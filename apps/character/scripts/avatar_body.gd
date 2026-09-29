class_name AvatarBody
extends Node3D
## Visual body of the character. Character owns movement, facing and the gesture
## clock; a body only animates in place from the shared AvatarState.
## Origin = feet, facing +Z (toward the camera), height normalised to BODY_HEIGHT.
##
## Gesture motion shared by all bodies is defined here in "character space"
## (x = the character's left, y = up, z = forward) relative to the gesturing
## shoulder, in units of arm reach, so any avatar size works.

const BODY_HEIGHT := 1.55
## The hand tip (IK end effector, hand_pos, where a held chalk touches the
## board) lies this far past the fingers, in world units.
const CHALK_TIP := 0.025

const NOD_ANGLE := deg_to_rad(16.0)
const NOD_PERIOD := 0.55
const TAP_PERIOD := 0.32
## Tap hand path: base offset and lift, in arm-reach units.
const TAP_BASE := Vector3(-0.2, -0.65, 0.6)
const TAP_LIFT := 0.3
## Throw hand path for the right hand: [phase, offset in arm-reach units].
const THROW_KEYS: Array = [
	[0.0, Vector3(-0.15, -0.85, 0.2)],
	[0.3, Vector3(-0.3, 0.45, -0.3)],
	[0.4, Vector3(-0.25, 0.55, -0.35)],
	[AvatarState.THROW_RELEASE, Vector3(-0.1, 0.25, 0.9)],
	[0.6, Vector3(0.25, -0.35, 0.7)],
	[1.0, Vector3(-0.1, -0.8, 0.25)],
]
## Default writing-hand offset (raised to board height beside the body) before
## the first ik_target arrives, in arm-reach units.
const WRITE_DEFAULT := Vector3(-0.55, 0.3, 0.55)

var state: AvatarState


## Damped spring on a float, integrated in fixed sub-steps so it stays stable at
## low frame rates. zeta < 1 overshoots and settles (follow-through), zeta = 1
## eases in and out without overshoot. Allocate once; step() allocates nothing.
class Spring:
	var value := 0.0
	var velocity := 0.0

	func step(target: float, omega: float, zeta: float, delta: float) -> float:
		var n := clampi(ceili(delta * 120.0), 1, 8)
		var h := delta / n
		for i in n:
			velocity += (omega * omega * (target - value) - 2.0 * zeta * omega * velocity) * h
			value += velocity * h
		return value

	func reset(to: float) -> void:
		value = to
		velocity = 0.0


## Damped spring on a Vector3 (see Spring).
class Spring3:
	var value := Vector3.ZERO
	var velocity := Vector3.ZERO

	func step(target: Vector3, omega: float, zeta: float, delta: float) -> Vector3:
		var n := clampi(ceili(delta * 120.0), 1, 8)
		var h := delta / n
		for i in n:
			velocity += (omega * omega * (target - value) - 2.0 * zeta * omega * velocity) * h
			value += velocity * h
		return value

	func reset(to: Vector3) -> void:
		value = to
		velocity = Vector3.ZERO


## Gaze life (cosmetic, randomised timing, no scenario): where the eyes and the
## head go, as (yaw toward the character's left, pitch up) in radians in the body
## frame. Eyes lead and the head follows only part of the way; eye contact with
## the user is broken by short glances away (usually with a blink), the face is
## held a little off-axis (3/4) while the eyes hold contact, micro-saccades keep
## the eyes alive, and without a look target she looks around. Held up by the
## collar she looks about in a fluster. Bodies apply head/eyes with their own
## limits and springs. update() allocates nothing.
class Gaze:
	## Eyelid closure added while relaxed (never a wide-open stare) and when looking down.
	const LID_SOFT := 0.14
	const LID_DOWN := 0.3

	## Outputs, valid after update().
	var eyes := Vector2.ZERO  ## where the eyes look
	var head := Vector2.ZERO  ## where the head turns
	var tilt := 0.0  ## head roll goal
	var twist := 0.0  ## upper-body turn goal (a 3/4 pose while idle)
	var lid := 0.0  ## extra eyelid closure 0..1
	var blink := false  ## a gaze shift asks for a blink now; the body clears it
	var away := false  ## glancing away from the look target (or, idle, from the user)
	## Diagnostics for tests: attention switches and micro-saccades so far.
	var shifts := 0
	var saccades := 0

	var _eye_reach := Vector2(0.18, 0.15)
	var _timer := 0.6
	var _dir := Vector2.ZERO
	var _dir_absolute := false
	var _bias := Vector2.ZERO
	var _saccade := Vector2.ZERO
	var _saccade_timer := 0.4
	var _twist_timer := 3.0
	var _twist_goal := 0.0
	var _hanging := false
	var _last_goal := Vector2.ZERO

	## eye_reach: how far (yaw, pitch) the eyes turn before the head must follow.
	func _init(eye_reach: Vector2) -> void:
		_eye_reach = eye_reach
		_timer = randf_range(0.8, 2.0)
		_twist_timer = randf_range(2.0, 5.0)

	## target: the commanded look direction (POINT), user: the camera direction.
	func update(delta: float, look: AvatarState.Look, target: Vector2, user: Vector2,
			focused: bool, talking: bool, walking: bool, hang: float) -> void:
		_timer -= delta
		var goal: Vector2
		var share := 0.5
		if hang > 0.5:
			if not _hanging or _timer <= 0.0:
				_hanging = true
				_flustered(user)
			goal = _dir
			share = 0.85
		else:
			if _hanging:
				_hanging = false
				_timer = 0.0
			if focused:
				if away:
					_contact(look == AvatarState.Look.POINT)
				_timer = maxf(_timer, 0.8)  # hold contact for a moment after the gesture
			elif _timer <= 0.0:
				_next(look, talking, walking)
			var base := user if look != AvatarState.Look.POINT else target
			if not away:
				goal = base
				share = 0.85 if look == AvatarState.Look.POINT else 0.5
			else:
				goal = _dir if _dir_absolute else base + _dir
				share = 0.65
		if goal.distance_to(_last_goal) > 0.1:
			shifts += 1
			blink = blink or randf() < (0.25 if _hanging else 0.7)
		_last_goal = goal
		# Micro-saccades: small quick jumps, faster while reading/writing or flustered.
		_saccade_timer -= delta
		if _saccade_timer <= 0.0:
			saccades += 1
			var amp := 0.05 if _hanging else 0.02
			_saccade = Vector2(randf_range(-amp, amp), randf_range(-amp, amp) * 0.6)
			_saccade_timer = randf_range(0.15, 0.35) if _hanging else randf_range(0.18, 0.5) if focused else randf_range(0.4, 1.4)
		eyes = goal + _saccade
		head = Vector2(_share_of(goal.x, share, _eye_reach.x), _share_of(goal.y, share, _eye_reach.y))
		if not away and not _hanging and look != AvatarState.Look.POINT:
			# Facing the user, hold the face a little off-axis; turned away, the
			# partial head turn already gives the 3/4 look.
			head += _bias * (1.0 - clampf(goal.length() / 0.2, 0.0, 1.0))
		# Idle 3/4 pose: now and then the upper body turns a little.
		_twist_timer -= delta
		if _twist_timer <= 0.0:
			_twist_timer = randf_range(3.0, 7.0)
			_twist_goal = 0.0 if randf() < 0.3 else randf_range(0.09, 0.19) * (1.0 if randf() < 0.5 else -1.0)
		var calm := not (focused or walking or talking or hang > 0.0)
		twist = _twist_goal if calm else 0.0
		lid = 0.0 if _hanging else LID_SOFT + LID_DOWN * clampf(-eyes.y / 0.35, 0.0, 1.0)

	## Head part of a gaze angle: `share` of it, more when the eyes cannot reach the rest.
	static func _share_of(angle: float, share: float, reach: float) -> float:
		return signf(angle) * maxf(absf(angle) * share, absf(angle) - reach)

	## Back to the look target, the face held a little off-axis (3/4).
	func _contact(point: bool) -> void:
		away = false
		_bias = Vector2.ZERO if point else Vector2(randf_range(0.05, 0.14) * (1.0 if randf() < 0.5 else -1.0), randf_range(-0.04, 0.03))
		tilt = randf_range(-0.07, 0.07) if randf() < 0.6 else 0.0

	func _glance(dir: Vector2, absolute: bool) -> void:
		away = true
		_dir = dir
		_dir_absolute = absolute
		tilt = randf_range(-0.05, 0.05)

	## Picks the next attention target and how long to hold it.
	func _next(look: AvatarState.Look, talking: bool, walking: bool) -> void:
		var side := 1.0 if randf() < 0.5 else -1.0
		if look == AvatarState.Look.FORWARD and not walking:
			# Idle without a target: look around, sometimes at the user.
			if randf() < 0.3:
				_contact(false)
				_timer = randf_range(1.0, 2.5)
			else:
				_glance(Vector2(side * randf_range(0.1, 0.5), randf_range(-0.3, 0.1)), true)
				_timer = randf_range(1.2, 3.5)
			return
		if away:
			_contact(look == AvatarState.Look.POINT)
			match look:
				AvatarState.Look.USER:
					_timer = randf_range(1.0, 2.2) if walking else randf_range(2.5, 6.0) if talking else randf_range(1.8, 4.5)
				AvatarState.Look.POINT:
					_timer = randf_range(3.0, 7.0)
				_:
					_timer = randf_range(1.0, 2.5)
			return
		if walking:
			# Look where she is going (ahead, a little down).
			_glance(Vector2(randf_range(-0.08, 0.08), randf_range(-0.2, -0.08)), true)
			_timer = randf_range(0.8, 1.8)
			return
		match look:
			AvatarState.Look.USER:
				var r := randf()
				if r < 0.45:
					_glance(Vector2(side * randf_range(0.1, 0.28), -randf_range(0.14, 0.28)), false)  # down, aside
				elif r < 0.8:
					_glance(Vector2(side * randf_range(0.2, 0.42), randf_range(-0.05, 0.05)), false)  # aside
				else:
					_glance(Vector2(side * randf_range(0.12, 0.3), randf_range(0.1, 0.2)), false)  # up, thinking
				_timer = randf_range(0.45, 1.3)
			_:
				_glance(Vector2(side * randf_range(0.05, 0.15), randf_range(-0.08, 0.05)), false)
				_timer = randf_range(0.4, 0.9)

	func _flustered(user: Vector2) -> void:
		var r := randf()
		var side := 1.0 if randf() < 0.5 else -1.0
		if r < 0.45:
			_glance(Vector2(randf_range(-0.45, 0.45), -randf_range(0.45, 0.75)), true)  # down: where is the floor?
		elif r < 0.7:
			_glance(user, true)  # at the user: put me down!
		elif r < 0.85:
			_glance(Vector2(randf_range(-0.3, 0.3), randf_range(0.3, 0.45)), true)  # up at the hand
		else:
			_glance(Vector2(side * randf_range(0.5, 0.8), randf_range(-0.2, 0.1)), true)
		tilt = randf_range(-0.14, 0.14)
		_timer = randf_range(0.25, 0.7)


## Switches between idle and walk locomotion.
func set_walking(_walking: bool) -> void:
	pass


## Height of the grab point (the nape, where the collar is held) above the feet, body space.
func grab_height() -> float:
	return BODY_HEIGHT * 0.8


## Advances the body by one frame. Called by Character after it updated state.
func animate(_delta: float) -> void:
	pass


## Bounds of the visible body in this node's parent space (used for hit_rect).
func local_bounds() -> AABB:
	return AABB(Vector3(-0.35, 0.0, -0.3), Vector3(0.7, BODY_HEIGHT, 0.6))


## World position of a hand's tip: the end of a held chalk, CHALK_TIP past the fingers.
func hand_tip(_hand: AvatarState.Hand) -> Vector3:
	return global_position + Vector3(0.0, BODY_HEIGHT * 0.5, 0.0)


## World direction from wrist to hand tip.
func hand_direction(_hand: AvatarState.Hand) -> Vector3:
	return Vector3.DOWN


## World position of a shoulder joint.
func shoulder(_hand: AvatarState.Hand) -> Vector3:
	return global_position + Vector3(0.0, BODY_HEIGHT * 0.75, 0.0)


## Mirrors a right-hand character-space offset for the given hand.
static func sided(offset: Vector3, hand: AvatarState.Hand) -> Vector3:
	return offset if hand == AvatarState.Hand.RIGHT else Vector3(-offset.x, offset.y, offset.z)


## Smooth 0..1..0 envelope of a one-shot gesture of the given duration.
static func envelope(t: float, duration: float, ramp_in: float, ramp_out: float) -> float:
	if duration <= 0.0:
		return 0.0
	var a := minf(ramp_in, duration * 0.3)
	var b := minf(ramp_out, duration * 0.3)
	return smoothstep(0.0, a, t) * smoothstep(0.0, b, duration - t)


## Head pitch (forward bow, radians) of a nod: a small lift (anticipation), then
## eased bows. Bodies run it through a spring for the rebound (follow-through).
static func nod_angle(t: float, duration: float) -> float:
	if duration <= 0.0:
		return 0.0
	var count := clampi(roundi(duration / NOD_PERIOD), 1, 3)
	var s := sin(PI * count * clampf(t / duration, 0.0, 1.0))
	var lift := sin(PI * clampf(t / 0.12, 0.0, 1.0)) if t < 0.12 else 0.0
	return NOD_ANGLE * (s * s - 0.2 * lift)


## Smooth, non-repeating wobble in about [-1, 1]: incommensurate sines with a
## per-channel phase. Cheap, deterministic, allocation-free idle noise.
static func wobble(t: float, channel: float) -> float:
	var a := 0.55 * sin(t + channel * 7.13) + 0.3 * sin(t * 2.237 + channel * 3.71)
	return a + 0.15 * sin(t * 4.853 + channel * 1.93)


## Height 0..1 of a stepping foot over its swing (0..1): it peels off gently,
## peaks early and is eased down, touching the ground with no vertical speed.
static func lift_curve(swing: float) -> float:
	var s := sin(PI * pow(clampf(swing, 0.0, 1.0), 0.8))
	return s * s


## Bend 0..1 of a dangling leg's back-kick at the given phase (cycles): the two
## legs alternate, each kicking for half a cycle.
static func kick(phase: float, side: float) -> float:
	return maxf(sin(TAU * phase + (0.0 if side > 0.0 else PI)), 0.0)


## Right-hand offset of a desk tap: quick strike down, slower lift, repeated.
static func tap_offset(t: float, duration: float) -> Vector3:
	var count := maxi(1, roundi(duration / TAP_PERIOD))
	var cycle := fposmod(clampf(t / maxf(duration, 0.001), 0.0, 1.0) * count, 1.0)
	var lift: float
	if cycle < 0.3:
		var k := cycle / 0.3
		lift = 1.0 - k * k
	else:
		lift = sin((cycle - 0.3) / 0.7 * PI * 0.5)
	return TAP_BASE + Vector3(0.0, TAP_LIFT * lift, 0.0)


## Right-hand offset of a throw at the given phase.
static func throw_offset(phase: float) -> Vector3:
	for i in range(1, THROW_KEYS.size()):
		var k1: Array = THROW_KEYS[i]
		if phase <= k1[0] or i == THROW_KEYS.size() - 1:
			var k0: Array = THROW_KEYS[i - 1]
			var f := smoothstep(k0[0], k1[0], phase)
			return (k0[1] as Vector3).lerp(k1[1], f)
	return THROW_KEYS[0][1]


## Chest twist (radians about up; negative turns the right shoulder back) of a throw.
static func throw_twist(phase: float) -> float:
	if phase < 0.4:
		return -deg_to_rad(22.0) * smoothstep(0.05, 0.35, phase)
	if phase < 0.6:
		return lerpf(-deg_to_rad(22.0), deg_to_rad(16.0), smoothstep(0.4, 0.5, phase))
	return deg_to_rad(16.0) * (1.0 - smoothstep(0.6, 1.0, phase))


## Eyelid closure of an auto-blink t seconds after it started: close 70 ms,
## hold 30 ms, open 120 ms (all divided by speed).
static func blink_curve(t: float, speed := 1.0) -> float:
	t *= speed
	if t < 0.07:
		return smoothstep(0.0, 0.07, t)
	if t < 0.1:
		return 1.0
	return 1.0 - smoothstep(0.1, 0.22, t)


## Next auto-blink delay: mostly 2.5-6 s, sometimes a quick double blink.
static func next_blink_delay() -> float:
	return randf_range(0.28, 0.4) if randf() < 0.18 else randf_range(2.5, 6.0)
