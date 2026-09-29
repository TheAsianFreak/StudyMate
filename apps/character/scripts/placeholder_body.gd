class_name PlaceholderBody
extends AvatarBody
## Built-in fallback body: a procedurally built chibi (about 1:3 head-to-body) with
## anime eyes, twin tails, cel shading and inverted-hull outlines. Used when no
## VRM avatar is available. Fully procedural, a simpler take on VrmBody:
##  - gait phase advances with the distance travelled (cadence follows speed);
##    a light walk with small quick steps, short moves shuffle with small
##    sideways lifts
##  - hips barely bob and sway, idle weight shifts, breathing, a small arm swing
##    that lags on a spring, twin tails that trail the motion
##  - single-segment arms aim at the hand target (point overshoots on a spring),
##    the head follows the shared gaze life (AvatarBody.Gaze) on a spring with
##    the irises leading, nods rebound
##  - held up by the collar: legs kick, arms flail; released: a squash landing
##  - eyes blink (sometimes twice, and with gaze shifts) by squashing, soft lids,
##    the mouth follows visemes and expressions ease in and out.

const OUTLINE_COLOR := Color(0.24, 0.16, 0.28)
const OUTLINE_WIDTH := 0.012
const HIP_Y := 0.58
## Legs hip-width apart, feet toed slightly out.
const LEG_X := 0.08
const TOE_OUT := 0.12
## Shoulder to hand tip (fingers at 0.355, plus CHALK_TIP).
const REACH := 0.38
const LOOK_YAW_MAX := deg_to_rad(50.0)
const LOOK_PITCH_MAX := deg_to_rad(25.0)
const LOOK_PLANE := 1.3
const IK_FOLLOW_RATE := 22.0
const FACE_OMEGA := 8.0
const MOUTH_RATE := 28.0
const SQUINT := {"happy": 0.5, "angry": 0.25, "sleepy": 0.6}

var _hips: Node3D
var _head: Node3D
var _legs: Array[Node3D] = []  # left, right
var _tails: Array[Node3D] = []  # left, right
var _arms: Dictionary = {}  # AvatarState.Hand -> Node3D pivot at the shoulder, hanging along -Y
var _arm_weight: Dictionary = {AvatarState.Hand.RIGHT: 0.0, AvatarState.Hand.LEFT: 0.0}
var _arm_target: Dictionary = {AvatarState.Hand.RIGHT: Vector3.ZERO, AvatarState.Hand.LEFT: Vector3.ZERO}
var _arm_spring: Dictionary = {AvatarState.Hand.RIGHT: AvatarBody.Spring3.new(), AvatarState.Hand.LEFT: AvatarBody.Spring3.new()}
var _swing_spring: Dictionary = {AvatarState.Hand.RIGHT: AvatarBody.Spring.new(), AvatarState.Hand.LEFT: AvatarBody.Spring.new()}
var _eyes: Array[Node3D] = []
var _irises: Array[Node3D] = []  # iris, pupil and shine of each eye (shift with the gaze)
var _mouth: Node3D
var _time := 0.0
var _phase := 0.0
var _walk := AvatarBody.Spring.new()
var _look := AvatarBody.Spring3.new()
var _nod := AvatarBody.Spring.new()
var _tilt := AvatarBody.Spring.new()
var _gaze := AvatarBody.Gaze.new(Vector2(0.14, 0.1))
var _eye_look := Vector2.ZERO
var _twist := AvatarBody.Spring.new()
var _hang_arms := AvatarBody.Spring.new()
var _land := AvatarBody.Spring.new()
var _kick_phase := 0.0
var _flail_phase := 0.0
var _relief_t := INF
var _shift := AvatarBody.Spring.new()
var _tail := AvatarBody.Spring.new()
var _squint := AvatarBody.Spring.new()
var _wide := AvatarBody.Spring.new()
var _smile := AvatarBody.Spring.new()
var _open := 0.0
var _wide_mouth := 0.0
var _round_mouth := 0.0
var _breath_phase := 0.0
var _breath_period := 3.8
var _shift_goal := 0.0
var _shift_timer := 3.0
var _blink_timer := 2.0
var _blink_t := 1.0
var _blink_speed := 1.0


func _ready() -> void:
	_build_rig()
	_hips = get_node("Hips")
	_legs = [get_node("Hips/LegL"), get_node("Hips/LegR")]
	_tails = [get_node("Hips/Head/TailL"), get_node("Hips/Head/TailR")]
	_breath_phase = randf()


func local_bounds() -> AABB:
	return transform * AABB(Vector3(-0.34, 0.0, -0.3), Vector3(0.68, 1.5, 0.6))


func hand_tip(hand: AvatarState.Hand) -> Vector3:
	return (_arms[hand] as Node3D).global_transform * Vector3(0.0, -REACH, 0.0)


func hand_direction(hand: AvatarState.Hand) -> Vector3:
	return ((_arms[hand] as Node3D).global_basis * Vector3.DOWN).normalized()


func shoulder(hand: AvatarState.Hand) -> Vector3:
	return (_arms[hand] as Node3D).global_position


## The nape: where the head sits on the body.
func grab_height() -> float:
	return HIP_Y + 0.42


## Gaze state (tests, diagnostics).
func gaze() -> AvatarBody.Gaze:
	return _gaze


func animate(delta: float) -> void:
	_time += delta
	var speed := state.velocity.length()
	var sh := state.shuffle
	var hang := smoothstep(0.0, 1.0, state.hang)
	var walk := clampf(_walk.step(1.0 if state.moving and speed > 0.02 else 0.0, 7.0, 1.0, delta), 0.0, 1.0)
	var calm := (1.0 - maxf(walk, 1.0 if state.is_hand_gesture() else 0.0)) * (1.0 - hang)
	# One gait cycle = two steps; step length grows with speed (unhurried cadence).
	var stride := lerpf(clampf(0.2 + 0.2 * speed, 0.2, 0.4), 0.12, sh)
	_phase = fposmod(_phase + speed * delta / (2.0 * stride), 1.0)
	var s := sin(TAU * _phase)
	_breath_phase += delta / _breath_period
	if _breath_phase >= 1.0:
		_breath_phase -= 1.0
		_breath_period = randf_range(3.2, 4.6)
	var breath := sin(TAU * _breath_phase)
	_idle_events(delta)
	var shift := _shift.step(_shift_goal * calm, 2.2, 1.0, delta)
	var fluster := state.fluster if state.grabbed else 0.3 * state.fluster
	_kick_phase = fposmod(_kick_phase + delta * 2.4 * (0.8 + 0.6 * fluster), 100.0)
	_flail_phase = fposmod(_flail_phase + delta * 1.5 * (0.7 + 0.8 * fluster), 100.0)
	if state.touchdown:
		_relief_t = 0.0
		_land.velocity -= minf(state.land_speed * 0.45, 0.9)
		_blink_t = 0.0
	_relief_t += delta
	var land := _land.step(0.0, 11.0, 0.5, delta)

	# Hips: a slight bob twice per cycle, a little sway, idle weight shift,
	# a hunch while held up, a squash on landing.
	var bob := absf(s) * lerpf(0.01, 0.006, sh) * walk + 0.012 * (breath * 0.5 + 0.5) * calm
	_hips.position = Vector3((0.004 * s * walk + 0.025 * shift) * (1.0 - hang), HIP_Y + bob * (1.0 - hang) + land, 0.0)
	_hips.rotation = Vector3(0.03 * walk * (1.0 - sh) + 0.12 * hang, 0.04 * s * walk * (1.0 - sh), -0.03 * s * walk * sh + 0.04 * shift)
	var twist := _twist.step(_gaze.twist, 2.2, 1.0, delta)
	_hips.rotation.y += twist * 0.6

	# Legs: forward swings when walking, small sideways lifts when shuffling;
	# held up, alternating back-kicks. Feet toed slightly out.
	for i in 2:
		var side := 1.0 if i == 0 else -1.0
		var leg := _legs[i]
		var walk_rot := Vector3(
			0.36 * s * side * walk * (1.0 - sh),
			side * TOE_OUT - twist * 0.6,  # the feet stay put when the upper body turns
			0.15 * maxf(0.0, s * side) * side * walk * sh)
		var kick := AvatarBody.kick(_kick_phase, side) * (0.3 + 0.7 * state.fluster) * (0.3 if state.airborne else 1.0)
		leg.rotation = walk_rot.lerp(Vector3(0.55 * kick, side * TOE_OUT - twist * 0.6, side * 0.06), hang)

	# Arms: swing a little against the legs, lagging on a spring; held up they
	# flail (raised and waving), falling they spread, landing they drop back.
	var flail := clampf(_hang_arms.step(state.hang, 10.0, 0.6, delta), -0.15, 1.0)
	for hand: AvatarState.Hand in _arms:
		var arm: Node3D = _arms[hand]
		var side := 1.0 if hand == AvatarState.Hand.LEFT else -1.0
		var swing := -0.26 * s * side * walk * (1.0 - sh) + 0.03 * wobble(_time * 0.6, side * 3.0)
		var out := 0.14 + 0.02 * breath + 0.12 * sh * walk
		if flail != 0.0:
			var ph := TAU * _flail_phase
			var wave := sin(ph + (0.0 if side > 0.0 else 2.4))
			var wave2 := sin(ph * 0.53 + side * 1.3)
			var f := state.fluster
			var f_swing := 0.6 * wave * f if not state.airborne else 0.2
			var f_out := 1.25 + 0.35 * wave2 * f if not state.airborne else 1.2
			swing = lerpf(swing, f_swing, flail)
			out = lerpf(out, f_out, flail)
		var lagged := (_swing_spring[hand] as AvatarBody.Spring).step(swing, 10.0, 0.5, delta)
		arm.rotation = Vector3(lagged, 0.0, side * out)
		_update_arm(hand, delta)

	# Head: gaze life (the irises lead, the head follows part way), nod
	# rebound, tilt; held up it stays nearer upright than the swinging body.
	_gaze.update(delta, state.look, _look_goal(), _dir_goal(Vector3.BACK), state.is_focused(),
		state.is_talking(), walk > 0.5 and sh < 0.5, state.hang)
	var head_goal := Vector3(clampf(_gaze.head.x, -LOOK_YAW_MAX, LOOK_YAW_MAX), clampf(_gaze.head.y, -LOOK_PITCH_MAX, LOOK_PITCH_MAX), 0.0)
	var look := _look.step(head_goal, 7.0 * (1.0 + 0.6 * hang), 0.85, delta)
	var eye_goal := Vector2(clampf(_gaze.eyes.x - look.x, -0.14, 0.14), clampf(_gaze.eyes.y - look.y, -0.1, 0.1))
	_eye_look = _eye_look.lerp(eye_goal, 1.0 - exp(-32.0 * delta))
	for iris in _irises:
		iris.position = Vector3(_eye_look.x * 0.07, _eye_look.y * 0.07, 0.0)
	var nod := _nod.step(nod_angle(state.gesture_time, state.gesture_duration) if state.gesture == "nod" else 0.0, 20.0, 0.42, delta)
	var tilt := _tilt.step(_gaze.tilt * maxf(1.0 - walk, hang) + 0.05 * wobble(_time * 0.7, 2.0) * calm, 3.0 + 4.0 * hang, 1.0, delta)
	_head.rotation = Vector3(nod - look.y + 0.03 * walk + 0.1 * hang, look.x - twist * 0.6, tilt - state.swing * 0.4 * hang)
	# Twin tails trail the hips and head (secondary motion).
	var trail := _tail.step(-_hips.position.x * 6.0 - look.x * 0.3 - state.swing * 0.8, 9.0, 0.35, delta)
	_tails[0].rotation.z = 0.05 * breath + trail
	_tails[1].rotation.z = -0.05 * breath + trail
	_update_face(delta)


func _idle_events(delta: float) -> void:
	_shift_timer -= delta
	if _shift_timer <= 0.0:
		_shift_timer = randf_range(3.5, 8.0)
		_shift_goal = 0.0 if randf() < 0.2 else -signf(_shift_goal + 0.01) * randf_range(0.4, 1.0)


## Unclamped (yaw toward the character's left, pitch up) to the commanded look target.
func _look_goal() -> Vector2:
	match state.look:
		AvatarState.Look.USER:
			return _dir_goal(Vector3.BACK)
		AvatarState.Look.POINT:
			var h := _head.global_position
			return _dir_goal(Vector3(state.look_point.x - h.x, state.look_point.y - h.y, LOOK_PLANE))
	return Vector2.ZERO


func _dir_goal(dir: Vector3) -> Vector2:
	var d := (global_basis.inverse() * dir).normalized()
	return Vector2(atan2(d.x, d.z), atan2(d.y, Vector2(d.x, d.z).length()))


# --- Gesture arm -------------------------------------------------------------

func _update_arm(hand: AvatarState.Hand, delta: float) -> void:
	var arm: Node3D = _arms[hand]
	var s := arm.global_position
	var goal_weight := 0.0
	var goal := Vector3.ZERO
	var mode := 0  # 0 direct, 1 follow, 2 spring
	var rate := 4.0
	if state.is_hand_gesture() and state.gesture_hand == hand and state.hang < 1.0:
		var t := state.gesture_time
		var d := state.gesture_duration
		match state.gesture:
			"write":
				goal_weight = 1.0
				mode = 1
				if state.has_ik_target:
					goal = state.ik_target
				else:
					goal = s + global_basis * sided(WRITE_DEFAULT, hand) * REACH
			"point":
				goal_weight = 1.0
				mode = 2
				rate = 6.0
				var to := state.point_target - s
				to.z = 0.0
				if t < 0.1:
					goal = s + global_basis * sided(Vector3(-0.1, -0.45, 0.35), hand) * REACH
				else:
					goal = s + (to.normalized() * 0.9 + Vector3(0.0, 0.0, 0.35)).normalized() * REACH
			"tap_desk":
				goal_weight = envelope(t, d, 0.15, 0.2)
				rate = 10.0
				goal = s + global_basis * sided(tap_offset(t, d), hand) * REACH
			"throw":
				goal_weight = envelope(t, d, 0.12, 0.25)
				rate = 12.0
				goal = s + global_basis * sided(throw_offset(state.gesture_phase()), hand) * REACH
	goal_weight *= 1.0 - state.hang  # held up, the arms flail instead
	var w: float = _arm_weight[hand]
	var spring: AvatarBody.Spring3 = _arm_spring[hand]
	if w <= 0.0 and goal_weight > 0.0:
		_arm_target[hand] = hand_tip(hand)
		spring.reset(hand_tip(hand))
	w = move_toward(w, goal_weight, delta * rate)
	_arm_weight[hand] = w
	if goal_weight > 0.0:
		match mode:
			1:
				_arm_target[hand] = (_arm_target[hand] as Vector3).lerp(goal, 1.0 - exp(-IK_FOLLOW_RATE * delta))
			2:
				_arm_target[hand] = spring.step(goal, 13.0, 0.72, delta)
			_:
				_arm_target[hand] = goal
	if w <= 0.0:
		return
	var to_target: Vector3 = _arm_target[hand] - s
	to_target.z = maxf(to_target.z, 0.08)  # keep the hand in front of the body
	var local_dir := (arm.get_parent() as Node3D).global_basis.inverse() * to_target
	if local_dir.length() < 1e-4:
		return
	var aim := Quaternion(Vector3.DOWN, local_dir.normalized())
	arm.quaternion = arm.quaternion.slerp(aim, smoothstep(0.0, 1.0, w))


# --- Face --------------------------------------------------------------------

func _update_face(delta: float) -> void:
	var w := state.emotion_weight
	var squint := _squint.step(float(SQUINT.get(state.emotion, 0.0)) * w, FACE_OMEGA, 1.0, delta)
	var wide := _wide.step(w if state.emotion == "surprised" else 0.0, FACE_OMEGA, 1.0, delta)
	var relief := smoothstep(0.1, 0.35, _relief_t) * (1.0 - smoothstep(1.3, 2.0, _relief_t))
	var smile := _smile.step(maxf(w if state.emotion == "happy" else 0.0, 0.5 * relief), FACE_OMEGA, 1.0, delta)
	var talking := state.viseme_age <= 0.2
	var v := state.visemes
	var aa: float = v.aa if talking else 0.0
	var ih: float = v.ih if talking else 0.0
	var ou: float = v.ou if talking else 0.0
	var ee: float = v.ee if talking else 0.0
	var oh: float = v.oh if talking else 0.0
	var km := 1.0 - exp(-MOUTH_RATE * delta)
	var open_goal := maxf(maxf(aa, oh * 0.8), maxf(ou * 0.5, maxf(ih, ee) * 0.4))
	if state.grabbed:
		open_goal = maxf(open_goal, state.hang * state.fluster * (0.14 + 0.1 * sin(TAU * 4.3 * _time)))
	_open = lerpf(_open, maxf(open_goal, wide * 0.6), km)
	_wide_mouth = lerpf(_wide_mouth, maxf(ee, ih), km)
	_round_mouth = lerpf(_round_mouth, maxf(ou, oh), km)

	_blink_timer -= delta
	if _blink_timer <= 0.0:
		_blink_t = 0.0
		_blink_timer = next_blink_delay()
		_blink_speed = randf_range(0.85, 1.2)
	if _gaze.blink:
		_gaze.blink = false
		if _blink_t > 0.35:
			_blink_t = 0.0
			_blink_timer = maxf(_blink_timer, 1.0)
	_blink_t += delta
	var lid := _gaze.lid * 0.6 * (1.0 - wide)
	var closed := maxf(squint, maxf(blink_curve(_blink_t, _blink_speed), lid) * (1.0 - smile))
	for eye in _eyes:
		eye.scale = Vector3(1.0 + wide * 0.1, maxf(0.08, (1.0 - closed) * (1.0 + wide * 0.2)), 1.0)
	_mouth.scale = Vector3(
		1.0 + _wide_mouth * 0.5 + smile * 0.5 - _round_mouth * 0.35,
		1.0 + _open * 4.0,
		1.0)


# --- Rig -------------------------------------------------------------------

func _build_rig() -> void:
	var hair := _material(Color(0.8, 0.66, 0.93))
	var hair_dark := _material(Color(0.62, 0.48, 0.82))
	var skin := _material(Color(1.0, 0.89, 0.82))
	var blazer := _material(Color(0.23, 0.26, 0.45))
	var shirt := _material(Color(0.98, 0.97, 0.95))
	var ribbon := _material(Color(0.93, 0.32, 0.45))
	var skirt := _material(Color(0.3, 0.3, 0.5))
	var sock := _material(Color(0.16, 0.15, 0.2))
	var eye_white := _material(Color(1, 1, 1), false)
	var iris := _material(Color(0.2, 0.62, 0.72), false)
	var pupil := _material(Color(0.1, 0.16, 0.3), false)
	var shine := _unshaded(Color(1, 1, 1))
	var lash := _unshaded(OUTLINE_COLOR)
	var blush := _unshaded(Color(1.0, 0.7, 0.75))

	var hips := _node(self, "Hips", Vector3(0, HIP_Y, 0))
	_cylinder(hips, skirt, 0.13, 0.25, 0.24, Vector3(0, 0.02, 0))
	_capsule(hips, blazer, 0.135, 0.4, Vector3(0, 0.24, 0))
	_box(hips, shirt, Vector3(0.1, 0.16, 0.04), Vector3(0, 0.32, 0.115))
	_box(hips, ribbon, Vector3(0.12, 0.05, 0.03), Vector3(0, 0.37, 0.14))

	var head := _node(hips, "Head", Vector3(0, 0.42, 0))
	_head = head
	_sphere(head, skin, Vector3(0.24, 0.23, 0.22), Vector3(0, 0.2, 0))
	# Hair: back volume, bangs, side locks and an ahoge.
	_sphere(head, hair, Vector3(0.26, 0.26, 0.25), Vector3(0, 0.24, -0.035))
	for i in 5:
		var x := -0.16 + 0.08 * i
		_sphere(head, hair, Vector3(0.07, 0.11, 0.05), Vector3(x, 0.33 - absf(x) * 0.25, 0.17), Vector3(0, 0, x * 0.8))
	for side: int in [1, -1]:
		_sphere(head, hair_dark, Vector3(0.05, 0.17, 0.05), Vector3(0.2 * side, 0.12, 0.09))
		var tail := _node(head, "TailL" if side == 1 else "TailR", Vector3(0.22 * side, 0.3, -0.06))
		_sphere(tail, hair_dark, Vector3(0.05, 0.05, 0.05), Vector3.ZERO)
		_sphere(tail, hair, Vector3(0.08, 0.28, 0.08), Vector3(0.06 * side, -0.24, -0.02), Vector3(0, 0, 0.25 * side))
	_sphere(head, hair, Vector3(0.02, 0.09, 0.02), Vector3(0.02, 0.5, 0.02), Vector3(0, 0, -0.5))

	# Face: big anime eyes with highlights, lashes and blush. Front is +Z.
	# Each eye sits under a pivot at its centre so blinks can squash it.
	for side: int in [1, -1]:
		var eye := _node(head, "EyeL" if side == 1 else "EyeR", Vector3(0.085 * side, 0.17, 0.2))
		_eyes.append(eye)
		_sphere(eye, eye_white, Vector3(0.05, 0.068, 0.02), Vector3.ZERO, Vector3.ZERO)
		var look := _node(eye, "Look", Vector3.ZERO)
		_irises.append(look)
		_sphere(look, iris, Vector3(0.04, 0.058, 0.02), Vector3(0, -0.008, 0.01), Vector3.ZERO)
		_sphere(look, pupil, Vector3(0.02, 0.03, 0.02), Vector3(0, -0.012, 0.022), Vector3.ZERO)
		_sphere(look, shine, Vector3(0.012, 0.015, 0.01), Vector3(-0.014, 0.02, 0.028), Vector3.ZERO)
		_box(eye, lash, Vector3(0.1, 0.012, 0.02), Vector3(0, 0.065, 0.005), Vector3(0, 0, -0.18 * side))
		_sphere(head, blush, Vector3(0.035, 0.015, 0.01), Vector3(0.13 * side, 0.1, 0.19), Vector3.ZERO)
	_mouth = _node(head, "Mouth", Vector3(0, 0.07, 0.212))
	_sphere(_mouth, lash, Vector3(0.018, 0.005, 0.008), Vector3.ZERO, Vector3.ZERO)

	for side: int in [1, -1]:
		var arm := _node(hips, "ArmL" if side == 1 else "ArmR", Vector3(0.16 * side, 0.36, 0))
		_arms[AvatarState.Hand.LEFT if side == 1 else AvatarState.Hand.RIGHT] = arm
		_capsule(arm, blazer, 0.045, 0.3, Vector3(0, -0.14, 0))
		_sphere(arm, skin, Vector3(0.04, 0.045, 0.04), Vector3(0, -0.31, 0))
		var leg := _node(hips, "LegL" if side == 1 else "LegR", Vector3(LEG_X * side, 0.0, 0))
		_capsule(leg, skin, 0.05, 0.3, Vector3(0, -0.15, 0))
		_capsule(leg, sock, 0.052, 0.3, Vector3(0, -0.4, 0))
		_sphere(leg, sock, Vector3(0.055, 0.04, 0.08), Vector3(0, -0.56, 0.025))


func _material(color: Color, outline := true) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.diffuse_mode = BaseMaterial3D.DIFFUSE_TOON
	m.specular_mode = BaseMaterial3D.SPECULAR_DISABLED
	m.rim_enabled = true
	m.rim = 0.25
	m.rim_tint = 0.8
	if outline:
		var o := _unshaded(OUTLINE_COLOR)
		o.cull_mode = BaseMaterial3D.CULL_FRONT
		o.grow = true
		o.grow_amount = OUTLINE_WIDTH
		m.next_pass = o
	return m


func _unshaded(color: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	return m


func _node(parent: Node3D, node_name: String, pos: Vector3) -> Node3D:
	var n := Node3D.new()
	n.name = node_name
	n.position = pos
	parent.add_child(n)
	return n


func _add_mesh(parent: Node3D, mesh: PrimitiveMesh, mat: Material, pos: Vector3, rot := Vector3.ZERO, scl := Vector3.ONE) -> void:
	mesh.material = mat
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.position = pos
	mi.rotation = rot
	mi.scale = scl
	parent.add_child(mi)


## Ellipsoid with the given radii. The mesh is built near its real size and only
## flattened by scale, so outline grow (applied before scale) keeps its width.
func _sphere(parent: Node3D, mat: Material, radii: Vector3, pos: Vector3, rot := Vector3.ZERO) -> void:
	var r := maxf(radii.x, radii.z)
	var m := SphereMesh.new()
	m.radius = r
	m.height = radii.y * 2.0
	m.radial_segments = 24
	m.rings = 12
	_add_mesh(parent, m, mat, pos, rot, Vector3(radii.x / r, 1.0, radii.z / r))


func _capsule(parent: Node3D, mat: Material, radius: float, height: float, pos: Vector3) -> void:
	var m := CapsuleMesh.new()
	m.radius = radius
	m.height = height
	_add_mesh(parent, m, mat, pos)


func _cylinder(parent: Node3D, mat: Material, top: float, bottom: float, height: float, pos: Vector3) -> void:
	var m := CylinderMesh.new()
	m.top_radius = top
	m.bottom_radius = bottom
	m.height = height
	_add_mesh(parent, m, mat, pos)


func _box(parent: Node3D, mat: Material, size: Vector3, pos: Vector3, rot := Vector3.ZERO) -> void:
	var m := BoxMesh.new()
	m.size = size
	_add_mesh(parent, m, mat, pos, rot)


