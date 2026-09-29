class_name Character
extends Node3D
## Moves and turns the character on the z = 0 plane (root = feet), runs the
## clock of the current gesture and hosts a swappable AvatarBody: the default
## VRM avatar, a user VRM or the built-in PlaceholderBody fallback.
## Command state lives in an AvatarState shared with the body. There is no
## scenario logic here: commands take effect as they arrive and the only timing
## is a gesture's own duration (and the throw's release point inside it), and
## the physics of being picked up (grab/release: swing, fall, landing).
## Node tree: Character (feet, or the grab point less the pivot while held)
## -> Hang (pendulum rotation about the grab point) -> Rig (facing) -> Body.

signal arrived
## Exactly one per accepted gesture: when its duration elapses, or at once when
## a newer gesture command supersedes it.
signal gesture_done(gesture_name: String)
## A chalk left the throwing hand (at the throw gesture's release point, or at
## once when no throw gesture is winding up).
signal chalk_released(strength: String, origin: Vector3)
## Back on her feet after a release (the landing reaction is over).
signal landed

const DEFAULT_AVATAR := "res://avatars/tsukuyomi-a.vrm"
## Walking, the body turns this far toward the travel direction (a 3/4-to-profile
## view keeps the legs' travel close to the on-screen travel: natural strides).
const FACE_ANGLE := deg_to_rad(65.0)
## Turning is a damped spring (eases in and out, no overshoot).
const TURN_OMEGA := 9.0
## Body turn toward the board while writing with the right hand: board on the
## hand's side (screen left) vs across the body (screen right).
const WRITE_TURN_NEAR := deg_to_rad(-20.0)
const WRITE_TURN_FAR := deg_to_rad(40.0)
const POINT_TURN := deg_to_rad(15.0)
## ik_target must cross the body centre by this much (world units) to switch sides.
const SIDE_HYSTERESIS := 0.08
## Moves shorter than this (world units, ~90 CSS px) are side-steps, not walks.
const SHUFFLE_DISTANCE := 0.56
## Time to reach cruise speed and to stop again (s); shorter moves use half their time.
const ACCEL_TIME := 0.35

## Grab (held up by the collar): the grab point follows the pointer on a
## critically damped spring and the body hangs below it as a damped pendulum
## driven by the grab point's acceleration (lag, overshoot, sway back).
const GRAB_OMEGA := 20.0
## Effective pendulum length (world units): longer than the body's ~0.35, so the
## sway reads unhurried (period ~1.5 s).
const SWING_LENGTH := 0.55
const SWING_DAMPING := 1.5
## Past SWING_SOFT a stiff spring cushions the swing; SWING_MAX is a hard stop.
const SWING_SOFT := deg_to_rad(45.0)
const SWING_MAX := deg_to_rad(70.0)
## Caps the grab point acceleration that drives the pendulum (wild flings).
const GRAB_ACCEL_MAX := 30.0
const GRAVITY := 9.8
## Released, she drops this far (world units, ~29 CSS px) onto her feet, never below the floor.
const DROP := 0.18
## Touchdown to the end of the landing reaction (`landed`).
const LAND_TIME := 0.6
## Resting flail level while held; pick-up and fast drags raise it to 1.
const FLUSTER_BASE := 0.45

var state := AvatarState.new()
## AvatarMeta of the current body (protocol shape).
var meta: Dictionary = AvatarLoader.meta_summary(null)

var _hang: Node3D
var _rig: Node3D
var _body: AvatarBody
var _held_chalk: Node3D
var _target := Vector3.ZERO
var _moving := false
var _facing := 0.0
var _walk_facing := 0.0
var _yaw_velocity := 0.0
var _released := false
var _pending_chalk := ""
var _look_mode := AvatarState.Look.FORWARD
var _look_point := Vector3.ZERO
var _gesture_gaze := false
var _write_side := -1.0
var _clock := 0.0
var _last_ik_time := -1.0
var _shuffle_goal := 0.0

# Current move: distance along _move_dir follows a velocity profile that ramps
# (smoothstep-shaped) from the speed at the start to a cruise speed and back to
# zero, arriving exactly at distance / requested speed.
var _move_from := Vector3.ZERO
var _move_dir := Vector3.RIGHT
var _move_distance := 0.0
var _move_time := 0.0
var _move_duration := 0.0
var _move_ramp := 0.0
var _move_v0 := 0.0
var _move_cruise := 0.0

# Grab and fall. _pivot is the Hang-space point the pendulum turns about: the
# nape while held, the middle of the body while falling, the feet while landing.
var _pivot := Vector3.ZERO
var _anchor := Vector3.ZERO
var _anchor_velocity := Vector3.ZERO
var _anchor_goal := Vector3.ZERO
var _twist := AvatarBody.Spring.new()
var _floor_y := -INF
var _fall_velocity := Vector3.ZERO
var _land_y := 0.0
# A move_to that arrived while held, falling or landing; it starts on landing.
var _deferred := false
var _deferred_target := Vector3.ZERO
var _deferred_speed := 1.0


func _ready() -> void:
	_hang = Node3D.new()
	_hang.name = "Hang"
	add_child(_hang)
	_rig = Node3D.new()
	_rig.name = "Rig"
	_hang.add_child(_rig)
	_held_chalk = ChalkThrow.make_chalk(1.0)
	_held_chalk.name = "HeldChalk"
	_held_chalk.visible = false
	add_child(_held_chalk)
	use_default()


func body() -> AvatarBody:
	return _body


## Loads the bundled default avatar, or the placeholder if it was not imported.
func use_default() -> Dictionary:
	var packed: PackedScene = null
	if ResourceLoader.exists(DEFAULT_AVATAR):
		packed = load(DEFAULT_AVATAR) as PackedScene
	var avatar: Node3D = packed.instantiate() as Node3D if packed != null else null
	if avatar == null:
		push_warning("Character: %s missing (run tools/prepare_assets.py); using placeholder" % DEFAULT_AVATAR)
		return use_placeholder()
	return use_vrm(avatar, avatar.get("vrm_meta"))


func use_placeholder() -> Dictionary:
	_swap_body(PlaceholderBody.new())
	meta = AvatarLoader.meta_summary(null)
	return meta


## Replaces the body with a VRM avatar scene. Returns the protocol AvatarMeta.
func use_vrm(avatar: Node3D, vrm_meta: Resource) -> Dictionary:
	var vrm_body := VrmBody.new()
	_swap_body(vrm_body)
	vrm_body.setup(avatar, vrm_meta)
	meta = AvatarLoader.meta_summary(vrm_meta)
	return meta


# --- Commands ------------------------------------------------------------------

## Walks (or side-steps, for short moves) to target, arriving after
## distance / speed seconds with eased acceleration and deceleration. A new
## move_to mid-way continues from the current speed. Held up, falling or
## landing, the move waits and starts once she stands again.
func move_to(target: Vector3, speed: float) -> void:
	if is_held():
		_deferred = true
		_deferred_target = target
		_deferred_speed = speed
		return
	var offset := target - position
	var distance := offset.length()
	_target = target
	_move_from = position
	_move_dir = offset / distance if distance > 1e-6 else Vector3.RIGHT
	_move_distance = distance
	_move_time = 0.0
	_move_duration = distance / maxf(speed, 1e-3)
	_move_v0 = maxf(state.velocity.dot(_move_dir), 0.0) if _moving else 0.0
	_move_ramp = minf(ACCEL_TIME, _move_duration * 0.5)
	if _move_ramp > 0.0 and _move_v0 * _move_ramp * 0.5 > distance:
		# Arriving too fast for the requested time: just brake to a stop.
		_move_ramp = 2.0 * distance / _move_v0
		_move_duration = _move_ramp
	_move_cruise = maxf((distance - _move_ramp * _move_v0 * 0.5) / maxf(_move_duration - _move_ramp, 1e-4), 0.0)
	if _move_duration <= _move_ramp:
		_move_cruise = 0.0
	_shuffle_goal = 1.0 if distance < SHUFFLE_DISTANCE else 0.0
	if not _moving:
		_moving = true
		_body.set_walking(true)
	state.moving = true


func set_pos(pos: Vector3) -> void:
	_end_hang()
	_deferred = false
	position = pos
	state.teleported = true
	state.velocity = Vector3.ZERO
	_stop_move()


## Picked up by the back of the collar at the pointer p (a world point on the
## character plane), or the holding hand moved. floor_y: the lowest world y her
## feet may reach (the window's bottom edge); the grab point stays above it.
func grab(p: Vector3, floor_y: float) -> void:
	_floor_y = floor_y
	if not state.grabbed:
		_stop_move()
		# Hang from the nape, keeping the current pose (standing, falling or landing).
		_repivot(Vector3(0.0, _body.grab_height(), 0.0))
		_anchor = position + _pivot
		_anchor_velocity = _fall_velocity if state.airborne else Vector3.ZERO
		_fall_velocity = Vector3.ZERO
		state.grabbed = true
		state.airborne = false
		state.land_time = -1.0
		state.fluster = 1.0
	_anchor_goal = Vector3(p.x, maxf(p.y, _floor_y + _pivot.y), 0.0)


## Let go: she drops a short way (DROP, not below the floor) and lands on her feet.
func release() -> void:
	if not state.grabbed:
		return
	state.grabbed = false
	state.airborne = true
	# position is where her feet would be hanging straight below the grab point.
	_land_y = maxf(position.y - DROP, _floor_y)
	_fall_velocity = Vector3(clampf(_anchor_velocity.x * 0.35, -1.5, 1.5), clampf(_anchor_velocity.y * 0.3, -1.0, 1.2), 0.0)
	# Falling, the body rights itself about its middle.
	_repivot(Vector3(0.0, _pivot.y * 0.55, 0.0))


## Held up, falling or landing (move_to waits meanwhile).
func is_held() -> bool:
	return state.grabbed or state.airborne or state.land_time >= 0.0


## World position of the grab point while held.
func grab_point() -> Vector3:
	return position + _pivot


func play_gesture(gesture_name: String, duration: float) -> void:
	if state.gesture != "":
		_finish_gesture()
	state.gesture = gesture_name
	state.gesture_time = 0.0
	state.gesture_duration = maxf(duration, 0.0)
	state.gesture_hand = AvatarState.Hand.RIGHT
	_released = false
	_gesture_gaze = gesture_name == "write" or gesture_name == "point"
	match gesture_name:
		"write":
			if state.has_ik_target:
				_write_side = 1.0 if state.ik_target.x > global_position.x else -1.0
			else:
				_write_side = -1.0
		"point":
			state.point_target = _resolve_point_target()
			if state.point_target.x > global_position.x:
				state.gesture_hand = AvatarState.Hand.LEFT


func set_ik_target(p: Vector3) -> void:
	# Stroke velocity for the wrist (direction, writing wiggle), lightly smoothed.
	var dt := _clock - _last_ik_time
	if state.has_ik_target and dt > 0.005 and dt < 0.3:
		state.ik_velocity = state.ik_velocity.lerp((p - state.ik_target) / dt, 0.5)
	_last_ik_time = _clock
	state.ik_target = p
	state.has_ik_target = true
	var dx := p.x - global_position.x
	if dx > SIDE_HYSTERESIS:
		_write_side = 1.0
	elif dx < -SIDE_HYSTERESIS:
		_write_side = -1.0


func look_at_point(p: Vector3) -> void:
	_look_mode = AvatarState.Look.POINT
	_look_point = p
	_gesture_gaze = false
	if state.gesture == "point":
		state.point_target = p


func look_at_user() -> void:
	_look_mode = AvatarState.Look.USER
	_gesture_gaze = false


func set_emotion(emotion_name: String, weight: float) -> void:
	state.emotion = emotion_name
	state.emotion_weight = 0.0 if emotion_name == "neutral" else clampf(weight, 0.0, 1.0)


func set_visemes(weights: Dictionary) -> void:
	for v: String in AvatarState.VISEMES:
		var w: Variant = weights.get(v, 0.0)
		state.visemes[v] = clampf(float(w), 0.0, 1.0) if (w is float or w is int) else 0.0
	state.viseme_age = 0.0


func throw_chalk(strength: String) -> void:
	_pending_chalk = strength
	if state.gesture != "throw" or _released:
		_release_chalk()


# --- Queries -----------------------------------------------------------------

func world_bounds() -> AABB:
	var box := _rig.global_transform * _body.local_bounds()
	box = box.expand(_body.hand_tip(AvatarState.Hand.RIGHT))
	return box.expand(_body.hand_tip(AvatarState.Hand.LEFT))


## World position of the gesturing hand's tip (the right hand when idle).
func hand_position() -> Vector3:
	return _body.hand_tip(state.gesture_hand)


func hand_gesture_active() -> bool:
	return state.is_hand_gesture()


## True while anything visibly changes because of a command.
func is_active() -> bool:
	return _moving or state.gesture != "" or state.viseme_age < 0.5 or _pending_chalk != "" \
		or absf(_yaw_velocity) > 0.05 or state.hang > 0.0 or is_held()


## Distance along the current move after t seconds (see _move_* fields).
func move_progress(t: float) -> float:
	if t >= _move_duration:
		return _move_distance
	var ramp := _move_ramp
	if ramp <= 0.0:
		return _move_distance
	var u := minf(t, ramp) / ramp
	var s := ramp * (_move_v0 * u + (_move_cruise - _move_v0) * (u * u * u - 0.5 * u * u * u * u))
	if t <= ramp:
		return s
	var cruise_end := _move_duration - ramp
	s += _move_cruise * (minf(t, cruise_end) - ramp)
	if t <= cruise_end:
		return s
	var w := (t - cruise_end) / ramp
	return s + ramp * _move_cruise * (w - (w * w * w - 0.5 * w * w * w * w))


# --- Frame -------------------------------------------------------------------

func _process(delta: float) -> void:
	var started := FrameProfiler.begin()
	_clock += delta
	_update_hang(delta)
	_update_motion(delta)
	_update_gaze()
	if state.gesture != "":
		state.gesture_time += delta
	state.viseme_age += delta
	state.ik_velocity *= exp(-6.0 * delta) if _clock - _last_ik_time > 0.1 else 1.0
	var animate_started := FrameProfiler.begin()
	_body.animate(delta)
	FrameProfiler.end(&"animate", animate_started)
	state.teleported = false
	state.touchdown = false
	if state.gesture == "throw" and not _released and state.gesture_phase() >= AvatarState.THROW_RELEASE:
		_released = true
		if _pending_chalk != "":
			_release_chalk()
	if state.gesture != "" and state.gesture_time >= state.gesture_duration:
		_finish_gesture()
	_update_held_chalk()
	FrameProfiler.end(&"character", started)


func _update_motion(delta: float) -> void:
	state.shuffle = move_toward(state.shuffle, _shuffle_goal if _moving else state.shuffle, delta * 5.0)
	if _moving:
		_move_time += delta
		var next := _move_from + _move_dir * move_progress(_move_time)
		state.velocity = (next - position) / maxf(delta, 1e-4)
		position = next
		if _move_time >= _move_duration:
			position = _target
			_moving = false
			state.moving = false
			state.velocity = Vector3.ZERO
			_body.set_walking(false)
			arrived.emit()
		elif state.shuffle < 0.5 and absf(_move_dir.x) > 0.3:
			_walk_facing = signf(_move_dir.x) * FACE_ANGLE
	if state.hang > 0.0 or state.land_time >= 0.0:
		_facing = 0.0  # held up she faces the viewer
	elif _moving and state.shuffle < 0.5:
		_facing = _walk_facing
	elif state.gesture == "write":
		_facing = WRITE_TURN_FAR if _write_side > 0.0 else WRITE_TURN_NEAR
	elif state.gesture == "point":
		_facing = POINT_TURN * (1.0 if state.point_target.x > global_position.x else -1.0)
	else:
		_facing = 0.0
	# Damped-spring turn: eases in and out (the body steps its feet around it).
	var steps := clampi(ceili(delta * 120.0), 1, 8)
	var h := delta / steps
	for i in steps:
		var error := wrapf(_facing - _rig.rotation.y, -PI, PI)
		_yaw_velocity += (TURN_OMEGA * TURN_OMEGA * error - 2.0 * TURN_OMEGA * _yaw_velocity) * h
		_rig.rotation.y += _yaw_velocity * h
	state.turn_speed = _yaw_velocity


## Held: the grab point chases the pointer and drives the pendulum. Falling:
## gravity, the body rights itself. Landed: the leftover tilt settles about the
## feet, then `landed` (or the move_to that came in meanwhile).
func _update_hang(delta: float) -> void:
	var goal := 1.0 if state.grabbed or state.airborne else 0.0
	state.hang = move_toward(state.hang, goal, delta * (8.0 if goal > state.hang else 10.0))
	if not is_held():
		return
	var n := clampi(ceili(delta * 120.0), 1, 8)
	var h := delta / n
	var theta := state.swing
	var omega := state.swing_velocity
	if state.grabbed:
		for i in n:
			var accel := GRAB_OMEGA * GRAB_OMEGA * (_anchor_goal - _anchor) - 2.0 * GRAB_OMEGA * _anchor_velocity
			_anchor_velocity += accel * h
			_anchor += _anchor_velocity * h
			# Pendulum with an accelerating pivot: the body lags the hand, overshoots, sways back.
			var drive := accel.limit_length(GRAB_ACCEL_MAX)
			var g := maxf(GRAVITY + drive.y, 2.0)
			var accel_theta := -(g * sin(theta) + drive.x * cos(theta)) / SWING_LENGTH - SWING_DAMPING * omega
			var over := absf(theta) - SWING_SOFT
			if over > 0.0:
				accel_theta -= signf(theta) * 250.0 * over + 12.0 * omega * clampf(over / 0.2, 0.0, 1.0)
			omega += accel_theta * h
			theta += omega * h
			if absf(theta) > SWING_MAX:
				theta = signf(theta) * SWING_MAX
				omega = 0.0 if omega * theta > 0.0 else omega
		position = _anchor - _pivot
		var speed := _anchor_velocity.length()
		state.fluster = maxf(move_toward(state.fluster, FLUSTER_BASE, delta * 0.6),
			FLUSTER_BASE + (1.0 - FLUSTER_BASE) * clampf(speed / 1.5, 0.0, 1.0))
		var twist_goal := clampf(-_anchor_velocity.x * 0.15, -0.4, 0.4) + 0.15 * AvatarBody.wobble(_clock * 1.7, 5.0) * state.fluster
		_twist.step(twist_goal, 6.0, 0.4, delta)
	else:
		# Falling (righting about the middle) or landed (settling about the feet).
		for i in n:
			omega += (-121.0 * theta - 16.5 * omega) * h
			theta += omega * h
		_twist.step(0.0, 9.0, 0.8, delta)
		state.fluster = move_toward(state.fluster, 0.0, delta * 2.0)
		if state.airborne:
			_fall_velocity.y -= GRAVITY * delta
			_fall_velocity.x *= exp(-3.0 * delta)
			position += _fall_velocity * delta
		else:
			state.land_time += delta
	state.swing = theta
	state.swing_velocity = omega
	state.grab_velocity = _anchor_velocity if state.grabbed else _fall_velocity
	var basis := Basis(Vector3.BACK, theta) * Basis(Vector3.UP, _twist.value)
	_hang.transform = Transform3D(basis, _pivot - basis * _pivot)
	if state.airborne and _fall_velocity.y <= 0.0 and position.y + _hang.transform.origin.y <= _land_y:
		_touch_down()
	elif state.land_time >= LAND_TIME:
		_finish_landing()


func _touch_down() -> void:
	state.airborne = false
	state.land_speed = -_fall_velocity.y
	state.land_time = 0.0
	state.touchdown = true
	_fall_velocity = Vector3.ZERO
	_repivot(Vector3.ZERO)
	position.y = _land_y


func _finish_landing() -> void:
	_end_hang()
	if _deferred:
		_deferred = false
		move_to(_deferred_target, _deferred_speed)
	else:
		landed.emit()


## Moves the pendulum's pivot to q (Hang space) without moving the body.
func _repivot(q: Vector3) -> void:
	var b := _hang.basis
	position += (_pivot - q) - b * (_pivot - q)
	_pivot = q
	_hang.transform = Transform3D(b, q - b * q)


## Straight up again (landing done, or set_pos).
func _end_hang() -> void:
	if _pivot != Vector3.ZERO or _hang.transform != Transform3D.IDENTITY:
		position += _hang.transform.origin  # keep the feet where they are
	_hang.transform = Transform3D.IDENTITY
	_pivot = Vector3.ZERO
	_twist.reset(0.0)
	state.grabbed = false
	state.airborne = false
	state.land_time = -1.0
	state.hang = 0.0
	state.swing = 0.0
	state.swing_velocity = 0.0
	state.fluster = 0.0
	state.grab_velocity = Vector3.ZERO


func _stop_move() -> void:
	if _moving:
		_moving = false
		state.moving = false
		state.velocity = Vector3.ZERO
		_body.set_walking(false)


## A write/point gesture looks at its own target until the next look_at command.
func _update_gaze() -> void:
	if _gesture_gaze and state.gesture == "write" and state.has_ik_target:
		state.look = AvatarState.Look.POINT
		state.look_point = state.ik_target
	elif _gesture_gaze and state.gesture == "point":
		state.look = AvatarState.Look.POINT
		state.look_point = state.point_target
	else:
		state.look = _look_mode
		state.look_point = _look_point


func _update_held_chalk() -> void:
	var holding := (state.gesture == "write" \
		or (state.gesture == "throw" and not _released and _pending_chalk != "")) and state.hang < 0.5
	state.holding_chalk = holding
	_held_chalk.visible = holding
	if not holding:
		return
	# The chalk's far end is the hand tip, so it touches the ik_target.
	var dir := _body.hand_direction(state.gesture_hand)
	var tip := _body.hand_tip(state.gesture_hand)
	_held_chalk.global_transform = Transform3D(Basis(Quaternion(Vector3.UP, dir)), tip - dir * ChalkThrow.CHALK_LENGTH * 0.5)


func _finish_gesture() -> void:
	var finished := state.gesture
	state.gesture = ""
	_gesture_gaze = false
	if finished == "throw" and _pending_chalk != "":
		_release_chalk()  # never swallow a requested throw
	gesture_done.emit(finished)


func _release_chalk() -> void:
	var strength := _pending_chalk
	_pending_chalk = ""
	chalk_released.emit(strength, _body.hand_tip(AvatarState.Hand.RIGHT))


func _resolve_point_target() -> Vector3:
	if _look_mode == AvatarState.Look.POINT:
		return _look_point
	if state.has_ik_target:
		return state.ik_target
	return global_position + Vector3(-0.9, 1.3, 0.0)


func _swap_body(new_body: AvatarBody) -> void:
	if _body != null:
		_rig.remove_child(_body)
		_body.queue_free()
	_body = new_body
	_body.name = "Body"
	_body.state = state
	state.teleported = true
	_rig.add_child(_body)
	_body.set_walking(_moving)
