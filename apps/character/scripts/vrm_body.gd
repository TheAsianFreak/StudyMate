class_name VrmBody
extends AvatarBody
## Body driven by a VRM avatar, runtime-loaded or editor-imported (godot-vrm
## renames bones to the humanoid profile in both cases; the original names are
## tried as a fallback). Everything is procedural, so any VRM works without
## per-model animation assets:
##  - legs: feet are planted in the world and step (walk, side-step shuffle,
##    settle and turning steps); two-bone leg IK keeps them there, so they never
##    slide. A light, dainty gait: small quick steps eased down onto the ground,
##    barely any bob or sway. Thigh-rigged skirt panels hang from the pelvis.
##  - torso/arms: breathing, lean with speed and acceleration, arm swing with a
##    lagging forearm (spring), relaxed wrists and curled fingers.
##  - head/eyes: gaze life (AvatarBody.Gaze): the eyes lead and the head turns
##    only partly, glances away and back with blinks, micro-saccades, soft lids,
##    idle look-around and 3/4 turns; stabilised against torso motion.
##  - held up by the collar (grab): legs kick, arms flail, head looks about;
##    released: falls onto the feet with a squash, a stumble and relief.
##  - gestures: analytic two-bone arm IK with anticipation, overshoot springs
##    and torso/head reactions; writing leans, twists, shifts the hips and raises
##    the shoulder to extend the reach, and the wrist follows the stroke.
##  - face: expressions (eased), visemes and blinks written to the blend shapes
##    godot-vrm baked into the avatar's expression animations.
## Rotations are authored in character space (forward/left/up) and converted to
## each bone's local frame from its rest pose. Per-frame work allocates nothing:
## bone rotations live in fixed slot arrays and limb IK is batched so the
## skeleton recomputes its global poses only four times a frame.

enum {
	B_HIPS, B_SPINE, B_CHEST, B_UPPER_CHEST, B_NECK, B_HEAD, B_L_EYE, B_R_EYE,
	B_L_SHOULDER, B_R_SHOULDER, B_L_UPPER_ARM, B_R_UPPER_ARM, B_L_LOWER_ARM,
	B_R_LOWER_ARM, B_L_HAND, B_R_HAND, B_COUNT,
}
const SLOT_BONES: Array[String] = [
	"Hips", "Spine", "Chest", "UpperChest", "Neck", "Head", "LeftEye", "RightEye",
	"LeftShoulder", "RightShoulder", "LeftUpperArm", "RightUpperArm", "LeftLowerArm",
	"RightLowerArm", "LeftHand", "RightHand",
]
const LIMB_BONES: Array[String] = [
	"LeftUpperLeg", "LeftLowerLeg", "LeftFoot", "RightUpperLeg", "RightLowerLeg", "RightFoot",
	"LeftMiddleProximal", "RightMiddleProximal", "LeftToes", "RightToes",
]
const FINGERS: Array[String] = ["Index", "Middle", "Ring", "Little"]
const FINGER_JOINTS: Array[String] = ["Proximal", "Intermediate", "Distal"]
## Full curl per joint (proximal, intermediate, distal) and per-finger scale.
const FINGER_MAX: Array[float] = [1.13, 1.48, 0.96]
const FINGER_SCALE: Array[float] = [0.8, 0.95, 1.05, 1.15]
const CURL_RELAXED := 0.3
const CURL_GRIP := 0.78
const CURL_FIST := 0.95

const ARM_DOWN := deg_to_rad(72.0)
const ELBOW_BEND := deg_to_rad(12.0)
const WALK_ELBOW := deg_to_rad(12.0)
## Walking, the arms swing a little, the hands close to the body.
const ARM_SWING := deg_to_rad(7.5)
const WALK_ARM_IN := deg_to_rad(3.0)
## Elbow flex per radian the upper arm leads its lagging forearm spring.
const ARM_LAG := 0.8
const WRIST_RELAX := deg_to_rad(10.0)

## Screen points are looked at on a plane this far (world units) in front of the head.
const LOOK_PLANE := 1.3
const LOOK_YAW_MAX := deg_to_rad(60.0)
const LOOK_PITCH_UP := deg_to_rad(25.0)
const LOOK_PITCH_DOWN := deg_to_rad(35.0)
## The head trails the eyes (eyes jump, the head follows on this spring).
const LOOK_OMEGA := 7.0
const NECK_SHARE := 0.35
const EYE_YAW_MAX := deg_to_rad(12.0)
const EYE_PITCH_MAX := deg_to_rad(10.0)
## Fast enough that gaze shifts and micro-saccades read as jumps.
const EYE_RATE := 32.0
## Fraction of the torso's rotation the neck undoes (keeps the gaze steady).
const HEAD_STABILISE := 0.85

## ik_target smoothing (1/s): the hand trails the pen by about 1/rate seconds.
const IK_FOLLOW_RATE := 22.0
## Elbow direction of the right arm in character space (out, down, back).
const POLE := Vector3(-0.6, -1.0, -0.15)
## Keep the writing hand at most this fraction of the reach in front of the shoulder.
const WRITE_MAX_FORWARD := 0.55
## Point: the hand pulls in (anticipation), then a spring throws it out past
## POINT_REACH to full extension and settles back (overshoot).
const POINT_REACH := 0.86
const POINT_OMEGA := 13.0
const POINT_ZETA := 0.72
const ANTICIPATION := 0.1

## Writing reach: past COMFORT x arm reach from the resting shoulder, the body
## shifts its hips, leans and bends toward the chalk and raises the shoulder.
const COMFORT := 0.85
const LEAN_MAX := deg_to_rad(26.0)
## Reaching low bends the spine (not the hips) and squats only a little, so the
## thighs stay under the skirt.
const BEND_MAX := deg_to_rad(65.0)
const TWIST_MAX := deg_to_rad(12.0)
const HIP_SHIFT_MAX := 0.07
const SQUAT_MAX := 0.04
const SHOULDER_RAISE_MAX := deg_to_rad(16.0)
const WRIST_WIGGLE_HZ := 7.5

## Gait, in world units scaled by leg length / REF_LEG. A light, graceful walk:
## moderate steps at an unhurried cadence, the knee folding in the swing, a soft
## heel-to-toe roll, feet on a narrow track toed slightly out, a gentle bob and
## no side-to-side waddle, a calm upper body; the thighs stay under a skirt (hip
## flexion stays under HIP_FLEX_MAX).
const REF_LEG := 0.8
const SHUFFLE_STEP_TIME := 0.24
## Longest step (world units x leg scale); faster than max step / min time the
## planted foot drifts with the body instead of the stance splaying.
const WALK_STEP_MAX := 0.45
const SHUFFLE_STEP_MAX := 0.2
const WALK_STEP_TIME_MIN := 0.12
const SHUFFLE_STEP_TIME_MIN := 0.15
const SETTLE_STEP_TIME := 0.3
const SETTLE_DIST := 0.03
const SETTLE_YAW := deg_to_rad(12.0)
const LIFT_WALK := 0.04
const LIFT_SHUFFLE := 0.012
const LIFT_SETTLE := 0.016
const MIN_FOOT_SEP := 0.07
const TOE_OUT := deg_to_rad(7.0)
## Standing feet apart, as a fraction of the hip joints' spacing.
const STANCE_WIDTH := 1.0
## Toes point down a little as the foot leaves the ground (toe-off).
const TOE_SWING := deg_to_rad(8.0)
## Feet are set down heel first (toes up this much), then roll flat.
const TOE_LAND := deg_to_rad(-8.0)
const ROLL_TIME := 0.12
## The heel lies this fraction of the foot length behind the ankle.
const HEEL_BACK := 0.3
const SOFT_KNEES := 0.003
const WALK_CROUCH := 0.0
const BOB_WALK := 0.009
const BOB_SHUFFLE := 0.001
## Walking, the feet land this fraction closer to the midline (a narrow, light track).
const WALK_NARROW := 0.4
## A trailing planted foot peels its heel up (toes stay down) this much before
## the pelvis has to dip to reach it (x leg scale): no bob at double support.
const HEEL_RISE_MAX := 0.04
## Pelvis-relative hip flexion the gait and the writing squat stay under.
const HIP_FLEX_MAX := deg_to_rad(26.0)

## Skirt panels rigged to the thighs (VRoid style) follow the thigh only this
## much and hang from the pelvis for the rest, so a swinging leg cannot split them.
const CLOTH_THIGH_FOLLOW := 0.35

## Held up by the collar: legs kick back alternately, arms wave or reach down,
## toes point, shoulders hunch; the landing squashes on a spring.
const KICK_HZ := 2.4
const FLAIL_HZ := 1.5
const HANG_TOE := deg_to_rad(38.0)
const HANG_SHRUG := deg_to_rad(12.0)
const LAND_DIP_MAX := 0.9  # units/s of pelvis kick at touchdown

## Idle life (cosmetic, randomised timing).
const IDLE_SHIFT := 0.026
const BREATH_CHEST := deg_to_rad(1.2)
const BREATH_SHOULDER := deg_to_rad(1.6)

const EMOTION_OMEGA := 7.0
const VISEME_RATE := 28.0
const VISEME_HOLD := 0.2
const SHAPE_MAX := 0.99999
const EMOTIONS: Array[String] = ["happy", "angry", "sad", "relaxed", "surprised"]
const CHANNELS: Array[String] = ["happy", "angry", "sad", "relaxed", "surprised", "eyes_closed", "surprised_mouth"]
const WEIGHT_KEYS: Array[String] = [
	"happy", "angry", "sad", "relaxed", "surprised", "blink", "blinkleft", "blinkright",
	"aa", "ih", "ou", "ee", "oh", "lookleft", "lookright", "lookup", "lookdown",
]


## An arm or a leg: bones, IK state and (legs) the stepping foot. Skeleton
## space unless noted.
class Limb:
	var is_leg := false
	var hand := AvatarState.Hand.RIGHT
	var side := 1.0  # character-space x: +1 left, -1 right
	var upper := -1
	var lower := -1
	var end := -1
	var parent := -1
	var len_upper := 0.0
	var len_lower := 0.0
	var len_tip := 0.0
	var tip_axis := Vector3.DOWN  # hand-bone local direction wrist -> finger tips
	var rest_body := Vector3.ZERO  # arms: shoulder, legs: foot home; body space, world units
	var hip_offset := Vector3.ZERO  # legs: UpperLeg rest origin - Hips rest origin
	var ankle := 0.0  # legs: rest ankle height, world units
	var foot_len := 0.1  # legs: ankle to toes, world units
	var heel := 0.0  # legs: heel rise of a trailing planted foot this frame, world units
	var need := 0.0  # legs: hip drop this foot alone would need, world units
	var planted_t := 1.0  # legs: seconds since the foot was set down (heel-to-toe roll)
	# legs: rest rotations and aiming frames (bone direction, bend-plane normal)
	# of thigh and shank; the IK rebuilds their rotation from these every frame,
	# so no twist carries over between frames (the knees cannot drift inward).
	var rest_upper_q := Quaternion.IDENTITY
	var rest_lower_q := Quaternion.IDENTITY
	var rest_upper_frame := Basis.IDENTITY
	var rest_lower_frame := Basis.IDENTITY
	var normal := Vector3.RIGHT  # per frame: normal of the leg's bend plane
	var end_rest := Quaternion.IDENTITY  # rest global rotation of the end bone
	var end_rest_local := Quaternion.IDENTITY
	# arm gesture state
	var weight := 0.0
	var target := Vector3.ZERO
	var spring := AvatarBody.Spring3.new()
	var tip := Vector3.ZERO
	var dir := Vector3.DOWN
	var fore_dir := Vector3.DOWN
	var hand_dir := Vector3.ZERO  # desired wrist -> tip direction; ZERO = straight wrist
	var goal_weight := 0.0
	var goal_target := Vector3.ZERO
	var goal_mode := 0  # 0 direct, 1 follow, 2 spring
	var goal_rate := 4.0
	var elbow := AvatarBody.Spring.new()
	var curl := AvatarBody.Spring.new()
	var index_curl := AvatarBody.Spring.new()
	var applied_curl := -1.0
	var applied_index := -1.0
	# leg stepping state (world, y = 0 on the ground)
	var pos := Vector3.ZERO
	var yaw := 0.0
	var swing := -1.0
	var swing_time := 0.3
	var lift := 0.0
	var from := Vector3.ZERO
	var to := Vector3.ZERO
	var from_yaw := 0.0
	# while moving: position along the travel track relative to home, plus a
	# residual (from standing) that fades out over the first step
	var u := 0.0
	var u_from := 0.0
	var u_to := 0.0
	var res := Vector3.ZERO
	var res_from := Vector3.ZERO
	# per-frame IK scratch
	var active := false
	var w := 1.0
	var aim := Vector3.ZERO
	var reach_point := Vector3.ZERO
	var b := 0.0
	var pole := Vector3.ZERO
	var end_goal := Quaternion.IDENTITY
	var p_upper := Vector3.ZERO
	var p_lower := Vector3.ZERO
	var p_end := Vector3.ZERO
	var q_upper := Quaternion.IDENTITY
	var q_parent := Quaternion.IDENTITY
	# legs: the solved thigh and its parent (pelvis), for the skirt panels
	var thigh_xf := Transform3D.IDENTITY
	var parent_xf := Transform3D.IDENTITY

	func reach() -> float:
		return len_upper + len_lower + len_tip


## Root bone of a spring chain parented to a thigh (a VRoid-style skirt panel).
class Cloth:
	var bone := -1
	var leg: Limb
	var rest_local := Transform3D.IDENTITY  # relative to the thigh
	var rel_hips := Transform3D.IDENTITY  # relative to the pelvis, at rest


var _skeleton: Skeleton3D
var _bones: Dictionary = {}  # humanoid name -> bone index
var _rest_local: Dictionary = {}  # bone index -> Quaternion
var _rest_global: Dictionary = {}  # bone index -> Quaternion
var _slot_idx := PackedInt32Array()
var _slot_rest_local: Array[Quaternion] = []
var _slot_rest_global: Array[Quaternion] = []
var _slot_rest_global_inv: Array[Quaternion] = []
var _q: Array[Quaternion] = []
var _arms: Dictionary = {}  # AvatarState.Hand -> Limb
var _legs: Array[Limb] = []
var _limbs: Array[Limb] = []
var _finger_idx: Array[PackedInt32Array] = [PackedInt32Array(), PackedInt32Array()]
var _finger_kind: Array[PackedInt32Array] = [PackedInt32Array(), PackedInt32Array()]
var _finger_rest_local: Array[Array] = [[], []]
var _finger_rest_global: Array[Array] = [[], []]
var _forward := Vector3.BACK  # character forward in skeleton space
var _left := Vector3.RIGHT  # character left in skeleton space
var _bounds := AABB()
var _base_y := 0.0
var _time := 0.0
var _eye_bones := false

# Frame context
var _gb := Transform3D.IDENTITY
var _skel_xf := Transform3D.IDENTITY
var _skel_inv := Transform3D.IDENTITY
var _scale := 1.0
var _body_yaw := 0.0
var _ground_y := 0.0
var _speed := 0.0
var _accel := Vector3.ZERO
var _prev_velocity := Vector3.ZERO
var _walk_w := 0.0
var _screen_axis := Vector3.BACK  # world +Z (toward the viewer) in skeleton space

# Hips and gait
var _hips := -1
var _hips_rest_pos := Vector3.ZERO  # local (parent space)
var _hips_rest_s := Vector3.ZERO  # skeleton space
var _hips_parent_inv := Basis.IDENTITY
var _leg_scale := 1.0
var _feet_ready := false
var _loco := false  # feet on travel tracks (moving) vs planted in the world (standing)
var _last_leg: Limb
var _last_step_start := -10.0
var _step_len := 0.3
var _hips_offset := Vector3.ZERO  # character frame, world units
var _last_axis := Vector3.ZERO  # travel track axis of the previous frame

# Springs and idle-life state
var _walk_spring := AvatarBody.Spring.new()
var _pelvis_spring := AvatarBody.Spring3.new()
var _look_spring := AvatarBody.Spring3.new()
var _nod_spring := AvatarBody.Spring.new()
var _tilt_spring := AvatarBody.Spring.new()
var _idle_twist_spring := AvatarBody.Spring.new()
var _shift_spring := AvatarBody.Spring.new()
var _lean_spring := AvatarBody.Spring.new()
var _bend_spring := AvatarBody.Spring.new()
var _twist_spring := AvatarBody.Spring.new()
var _squat_spring := AvatarBody.Spring.new()
var _raise_spring := AvatarBody.Spring.new()
var _hip_shift_spring := AvatarBody.Spring3.new()
var _gesture_twist := AvatarBody.Spring.new()
var _look := Vector2.ZERO
var _eye := Vector2.ZERO
var _gaze := AvatarBody.Gaze.new(Vector2(EYE_YAW_MAX, EYE_PITCH_MAX) * 0.85)
var _breath := 0.0
var _breath_phase := 0.0
var _breath_period := 3.8
var _shift := 0.0
var _shift_goal := 0.0
var _shift_timer := 3.0
var _lean := 0.0
var _bend := 0.0
var _twist := 0.0
var _squat := 0.0
var _raise := 0.0
var _hip_shift := Vector3.ZERO
var _lean_lever := 0.4

# Held up by the collar and landing
var _grab_height := BODY_HEIGHT * 0.8
var _hang_arms := AvatarBody.Spring.new()  # arm blend, follows through on landing
var _land_spring := AvatarBody.Spring.new()  # pelvis dip at touchdown
var _kick_phase := 0.0
var _flail_phase := 0.0
var _relief_t := INF  # seconds since touchdown (relieved face)
var _cloth: Array[Cloth] = []

# Face: expression name (lower case) -> Array of [slot, blend shape index, weight].
var _expr: Dictionary = {}
var _override_blink: Dictionary = {}  # expression -> "none" | "block" | "blend"
var _override_mouth: Dictionary = {}
var _slots: Array[MeshInstance3D] = []
var _slot_used: Array[PackedInt32Array] = []
var _slot_acc: Array[Array] = []
var _slot_last: Array[Array] = []
var _channels: Dictionary = {}
var _channel_vel: Dictionary = {}
var _emotion_goal: Dictionary = {}
var _weights: Dictionary = {}
var _mouth: Dictionary = {"aa": 0.0, "ih": 0.0, "ou": 0.0, "ee": 0.0, "oh": 0.0}
var _blink_timer := 2.0
var _blink_t := 1.0
var _blink_speed := 1.0


## Takes ownership of an avatar scene (AvatarLoader result or instantiated import).
func setup(avatar: Node3D, meta: Resource) -> void:
	for channel: String in CHANNELS:
		_channels[channel] = 0.0
		_channel_vel[channel] = 0.0
		_emotion_goal[channel] = 0.0
	for key: String in WEIGHT_KEYS:
		_weights[key] = 0.0
	_q.resize(B_COUNT)
	_q.fill(Quaternion.IDENTITY)
	add_child(avatar)
	if not FrameProfiler.flags.has("nomerge"):
		for mesh_instance: Node in avatar.find_children("*", "MeshInstance3D", true, false):
			merge_surfaces(mesh_instance as MeshInstance3D)
	_skeleton = _find_skeleton(avatar)
	if _skeleton == null:
		push_warning("VrmBody: no Skeleton3D, avatar will not animate")
	else:
		_map_bones(meta)
		_detect_orientation(avatar)
	_normalize(avatar)
	if _skeleton != null:
		_setup_limbs()
		_setup_fingers()
		_setup_cloth(avatar)
	_setup_expressions(avatar)
	FrameProfiler.bracket_modifiers(_skeleton, &"modifiers")
	if FrameProfiler.flags.has("nosprings"):
		for node in avatar.find_children("*", "", true, false):
			if node.name == &"secondary":
				node.queue_free()
		for node in _skeleton.get_children(true):
			if node.name == &"VRM_internal_skeleton_modifier":
				node.queue_free()
	if FrameProfiler.flags.has("hidehair"):
		for node in avatar.find_children("Hair*", "MeshInstance3D", true, false):
			(node as MeshInstance3D).visible = false
	_blink_timer = randf_range(1.0, 3.0)
	_breath_phase = randf()
	_shift_timer = randf_range(1.5, 4.0)


func local_bounds() -> AABB:
	return transform * _bounds


func grab_height() -> float:
	return _grab_height


## Gaze state (tests, diagnostics).
func gaze() -> AvatarBody.Gaze:
	return _gaze


## Current (head, eyes) look angles: head (yaw, pitch) relative to the body and
## the eyes' extra turn on top of it (tests, diagnostics).
func look_angles() -> PackedVector2Array:
	return PackedVector2Array([_look, _eye])


## Number of thigh-parented skirt panels that hang from the pelvis.
func cloth_count() -> int:
	return _cloth.size()


func hand_tip(hand: AvatarState.Hand) -> Vector3:
	var arm: Limb = _arms.get(hand)
	if arm == null:
		return super(hand)
	return _skeleton.global_transform * arm.tip


func hand_direction(hand: AvatarState.Hand) -> Vector3:
	var arm: Limb = _arms.get(hand)
	if arm == null:
		return super(hand)
	return (_skeleton.global_transform.basis * arm.dir).normalized()


func shoulder(hand: AvatarState.Hand) -> Vector3:
	var arm: Limb = _arms.get(hand)
	if arm == null:
		return super(hand)
	return _skeleton.global_transform * _skeleton.get_bone_global_pose(arm.upper).origin


## World position of a foot's ankle target (tests, diagnostics); planted feet stay put.
func foot_position(left: bool) -> Vector3:
	for leg in _legs:
		if (leg.side > 0.0) == left:
			return Vector3(leg.pos.x, _ground_y + leg.ankle, leg.pos.z)
	return global_position


## True while a foot is in the air.
func foot_swinging(left: bool) -> bool:
	for leg in _legs:
		if (leg.side > 0.0) == left:
			return leg.swing >= 0.0
	return false


## Hips offset from rest in the character frame (world units): bob, sway, shifts.
func pelvis_offset() -> Vector3:
	return _hips_offset


## Lower-case names of the expressions found on this avatar.
func expression_names() -> Array:
	return _expr.keys()


func animate(delta: float) -> void:
	if _skeleton == null or FrameProfiler.flags.has("static"):
		return
	_time += delta
	var started := FrameProfiler.begin()
	_read_frame(delta)
	_idle_life(delta)
	_update_write_reach(delta)
	_update_feet(delta)
	_body_pose(delta)
	_apply_fk()
	FrameProfiler.end(&"pose", started)
	started = FrameProfiler.begin()
	for arm: Limb in _arms.values():
		_update_arm(arm, delta)
	_setup_legs_ik()
	_solve_limbs()
	_update_cloth()
	_update_fingers(delta)
	FrameProfiler.end(&"arms", started)
	started = FrameProfiler.begin()
	if not FrameProfiler.flags.has("noface"):
		_update_face(delta)
	FrameProfiler.end(&"face", started)


# --- Frame context and idle life -------------------------------------------

func _read_frame(delta: float) -> void:
	_gb = global_transform
	_skel_xf = _skeleton.global_transform
	_skel_inv = _skel_xf.affine_inverse()
	_scale = _skel_xf.basis.get_scale().x
	_body_yaw = atan2(_gb.basis.z.x, _gb.basis.z.z)
	_ground_y = _gb.origin.y - position.y
	_screen_axis = (_skel_inv.basis * Vector3.BACK).normalized()
	var velocity := state.velocity
	_speed = velocity.length()
	var raw_accel := (velocity - _prev_velocity) / maxf(delta, 1e-3)
	_accel = _accel.lerp(raw_accel, 1.0 - exp(-8.0 * delta))
	_prev_velocity = velocity
	var moving := 1.0 if state.moving and _speed > 0.02 else 0.0
	_walk_w = clampf(_walk_spring.step(moving, 7.0, 1.0, delta), 0.0, 1.0)


## Breathing and weight shifts: cosmetic, randomised (gaze life is in _body_pose).
func _idle_life(delta: float) -> void:
	_breath_phase += delta / _breath_period
	if _breath_phase >= 1.0:
		_breath_phase -= 1.0
		_breath_period = randf_range(3.2, 4.6)
	_breath = sin(TAU * _breath_phase)
	var calm := (1.0 - maxf(_walk_w, 1.0 if state.is_hand_gesture() else 0.0)) * (1.0 - state.hang)
	_shift_timer -= delta
	if _shift_timer <= 0.0:
		_shift_timer = randf_range(3.5, 8.0)
		_shift_goal = 0.0 if randf() < 0.2 else -signf(_shift_goal + 0.01) * randf_range(0.4, 1.0)
	_shift = _shift_spring.step(_shift_goal * calm, 2.2, 1.0, delta)
	var fluster := state.fluster if state.grabbed else 0.3 * state.fluster
	# Wrapped at 100 so every phase multiple used below stays continuous.
	_kick_phase = fposmod(_kick_phase + delta * KICK_HZ * (0.8 + 0.6 * fluster), 100.0)
	_flail_phase = fposmod(_flail_phase + delta * FLAIL_HZ * (0.7 + 0.8 * fluster), 100.0)
	if state.touchdown:
		_relief_t = 0.0
		_land_spring.velocity -= minf(state.land_speed * 0.45, LAND_DIP_MAX) * _leg_scale
		_blink_t = 0.0  # eyes squeeze shut on impact
		_blink_timer = next_blink_delay()
	_relief_t += delta


func _update_write_reach(delta: float) -> void:
	var lean := 0.0
	var bend := 0.0
	var twist := 0.0
	var squat := 0.0
	var raise := 0.0
	var shift := Vector3.ZERO
	var arm: Limb = _arms.get(state.gesture_hand)
	if state.gesture == "write" and arm != null and state.has_ik_target:
		var w := smoothstep(0.0, 1.0, arm.weight)
		var s := _gb * arm.rest_body
		var t := state.ik_target
		var d := Vector2(t.x - s.x, t.y - s.y)
		var reach := arm.reach() * _scale
		var dist := d.length()
		twist = clampf(d.x / reach, -1.0, 1.0) * TWIST_MAX * w
		if dist > reach * COMFORT:
			var need := d * ((dist - reach * COMFORT) / dist)
			var shift_x := clampf(need.x * 0.35, -HIP_SHIFT_MAX, HIP_SHIFT_MAX)
			shift = Vector3(shift_x * w, 0.0, 0.0)
			lean = clampf(asin(clampf((need.x - shift_x) / _lean_lever, -0.95, 0.95)), -LEAN_MAX, LEAN_MAX) * w
			if need.y < 0.0:
				bend = clampf(-need.y * 3.4 / _lean_lever, 0.0, BEND_MAX) * w
				squat = clampf(-need.y * 0.35, 0.0, SQUAT_MAX) * w
			else:
				raise = clampf(need.y / (reach * 0.2), 0.0, 1.0) * SHOULDER_RAISE_MAX * w
		if t.y > s.y:
			raise = maxf(raise, clampf((t.y - s.y) / reach, 0.0, 1.0) * SHOULDER_RAISE_MAX * 0.6 * w)
	_lean = _lean_spring.step(lean, 8.0, 0.9, delta)
	_bend = _bend_spring.step(bend, 8.0, 0.9, delta)
	_twist = _twist_spring.step(twist, 7.0, 0.9, delta)
	_squat = _squat_spring.step(squat, 8.0, 0.9, delta)
	_raise = _raise_spring.step(raise, 9.0, 0.8, delta)
	_hip_shift = _hip_shift_spring.step(shift, 7.0, 0.9, delta)


# --- Feet ------------------------------------------------------------------

func _home(leg: Limb) -> Vector3:
	var h := _gb * leg.rest_body
	h.y = 0.0
	return h


## Home of a foot while walking: closer to the midline (a narrow, light track).
func _track_home(leg: Limb) -> Vector3:
	var k := 1.0 - WALK_NARROW * (1.0 - state.shuffle)
	var h := _gb * Vector3(leg.rest_body.x * k, leg.rest_body.y, leg.rest_body.z)
	h.y = 0.0
	return h


func _other_leg(leg: Limb) -> Limb:
	return _legs[1] if leg == _legs[0] else _legs[0]


## Feet. Standing, they are planted in the world and take a settling step when
## off their home spot or twisted by a turn. Moving, each foot rides a track
## along the travel axis (the facing when walking, across it when side-stepping):
## planted feet slide back along the track exactly as fast as the body advances,
## so their screen position never changes, and the feet alternate with step
## length = speed x step time, landing half a step ahead.
func _update_feet(delta: float) -> void:
	if _legs.size() < 2:
		return
	if state.teleported or not _feet_ready:
		for leg in _legs:
			leg.pos = _home(leg)
			leg.yaw = _body_yaw + leg.side * TOE_OUT
			leg.swing = -1.0
		_feet_ready = true
		_loco = false
		_last_leg = null
	if state.touchdown:
		# Landing: the feet plant where the dangling ankles are; settle steps
		# (a stumble) bring them home afterwards.
		for leg in _legs:
			var ankle := _skel_xf * _skeleton.get_bone_global_pose(leg.end).origin
			leg.pos = Vector3(ankle.x, 0.0, ankle.z)
			leg.yaw = _body_yaw + leg.side * TOE_OUT
			leg.swing = -1.0
		_loco = false
		_last_leg = null
	if state.hang > 0.0:
		for leg in _legs:
			leg.swing = -1.0  # no stepping in the air (or while the landing blends in)
			leg.heel = 0.0
		_loco = false
		return
	for leg in _legs:
		leg.planted_t += delta
	var moving := state.moving and _speed > 0.02
	var swinging := _legs[0].swing >= 0.0 or _legs[1].swing >= 0.0
	if moving and not _loco:
		var axis := _track_axis()
		for leg in _legs:
			var rel := leg.pos - _track_home(leg)
			leg.u = rel.dot(axis)
			leg.res = rel - axis * leg.u
		_loco = true
	elif not moving and _loco and not swinging:
		_loco = false
	if _loco:
		_track_feet(delta, moving)
	else:
		_stand_feet(delta)


func _track_axis() -> Vector3:
	var vx := state.velocity.x
	var forward := Vector3(_gb.basis.z.x, 0.0, _gb.basis.z.z).normalized()
	var lateral := Vector3(_gb.basis.x.x, 0.0, _gb.basis.x.z).normalized()
	forward *= 1.0 if forward.x * vx >= 0.0 else -1.0
	lateral *= 1.0 if lateral.x * vx >= 0.0 else -1.0
	var axis := forward.lerp(lateral, state.shuffle).normalized()
	if absf(axis.x) < 0.35:
		axis = lateral if absf(lateral.x) > absf(forward.x) else forward
	return axis


func _track_feet(delta: float, moving: bool) -> void:
	var axis := _track_axis()
	var track_speed := state.velocity.x / axis.x if absf(axis.x) > 0.2 else 0.0
	var cadence := maxf(absf(track_speed), _speed)
	var sh := state.shuffle
	var max_step := lerpf(WALK_STEP_MAX, SHUFFLE_STEP_MAX, sh) * _leg_scale
	var length := minf(lerpf((0.31 + 0.15 * cadence) * REF_LEG, 0.16, sh) * _leg_scale, max_step)
	var step_time := lerpf(clampf(length / maxf(cadence, 0.05), 0.12, 0.42), SHUFFLE_STEP_TIME, sh)
	step_time = maxf(minf(step_time, max_step / maxf(absf(track_speed), 1e-3)),
		lerpf(WALK_STEP_TIME_MIN, SHUFFLE_STEP_TIME_MIN, sh))
	_step_len = maxf(minf(absf(track_speed) * step_time, max_step), 0.1 * _leg_scale)
	var reach := max_step * 0.75
	# Hurry the step when the planted foot is about to be left behind.
	var hurry := 1.0
	for leg in _legs:
		if leg.swing < 0.0:
			hurry = maxf(hurry, 1.0 + 2.5 * clampf((absf(leg.u) / reach - 0.6) / 0.4, 0.0, 1.0))
	var swinging := false
	var switched := axis.dot(_last_axis) < 0.97
	_last_axis = axis
	for leg in _legs:
		if leg.swing < 0.0:
			# Planted: its screen x is fixed; the track position follows from it
			# (so turning the body cannot drag it), drifting only past reach.
			var home := _track_home(leg)
			if switched:
				# The track turned (the body turning into the walk): re-split the
				# foot's offset along the new axis so it does not jump or drift.
				var rel := leg.pos - home
				rel.y = 0.0
				leg.u = rel.dot(axis)
				leg.res = rel - axis * leg.u
			if absf(axis.x) > 0.2:
				leg.u = clampf((leg.pos.x - home.x - leg.res.x) / axis.x, -reach, reach)
			else:
				leg.u = clampf(leg.u - track_speed * delta, -reach, reach)
			continue
		# Adapt to speed changes mid-step (starting, stopping, re-planned moves).
		leg.swing_time = step_time
		leg.u_to = clampf(track_speed * step_time * 0.5, -reach, reach)
		leg.swing = minf(leg.swing + delta * hurry / step_time, 1.0)
		var f := smoothstep(0.0, 1.0, leg.swing)
		leg.u = lerpf(leg.u_from, leg.u_to, f)
		leg.res = leg.res_from * (1.0 - f)
		leg.yaw = lerp_angle(leg.from_yaw, _body_yaw + leg.side * TOE_OUT, f)
		if leg.swing >= 1.0:
			leg.swing = -1.0
			leg.planted_t = 0.0
		else:
			swinging = true
	for leg in _legs:
		leg.pos = _track_home(leg) + axis * leg.u + leg.res
		leg.pos.y = 0.0
	if swinging or not moving:
		return
	var leg := _next_leg(axis)
	leg.u_from = leg.u
	leg.res_from = leg.res
	leg.u_to = clampf(track_speed * step_time * 0.5, -reach, reach)
	leg.from_yaw = leg.yaw
	leg.swing = 0.0
	leg.swing_time = step_time
	leg.lift = lerpf(LIFT_WALK * clampf(cadence / 1.0, 0.8, 1.2), LIFT_SHUFFLE, sh) * _leg_scale
	_last_leg = leg
	_last_step_start = _time


func _stand_feet(delta: float) -> void:
	var swinging := false
	for leg in _legs:
		if leg.swing < 0.0:
			continue
		leg.swing = minf(leg.swing + delta / leg.swing_time, 1.0)
		leg.to = _landing(leg)
		var f := smoothstep(0.0, 1.0, leg.swing)
		leg.pos = leg.from.lerp(leg.to, f)
		leg.yaw = lerp_angle(leg.from_yaw, _body_yaw + leg.side * TOE_OUT, f)
		if leg.swing >= 1.0:
			leg.swing = -1.0
			leg.planted_t = 0.0
		else:
			swinging = true
	if swinging:
		return
	var worst: Limb = null
	var worst_error := 1.0
	for leg in _legs:
		var error := (leg.pos - _home(leg)).length() / (SETTLE_DIST * _leg_scale)
		error = maxf(error, absf(angle_difference(leg.yaw, _body_yaw + leg.side * TOE_OUT)) / SETTLE_YAW)
		if error > worst_error:
			worst = leg
			worst_error = error
	if worst != null:
		worst.from = worst.pos
		worst.from_yaw = worst.yaw
		worst.swing = 0.0
		worst.swing_time = SETTLE_STEP_TIME
		worst.lift = LIFT_SETTLE * _leg_scale
		worst.to = _landing(worst)
		_last_leg = worst
		_last_step_start = _time


## Where a settling foot lands: its home, never crossing the other foot.
func _landing(leg: Limb) -> Vector3:
	var p := _home(leg)
	var lateral := Vector3(_gb.basis.x.x, 0.0, _gb.basis.x.z).normalized()
	var separation := (p - _other_leg(leg).pos).dot(lateral) * leg.side
	var min_separation := MIN_FOOT_SEP * _leg_scale
	if separation < min_separation:
		p += lateral * leg.side * (min_separation - separation)
	p.y = 0.0
	return p


## Alternate feet; the first step of a move is taken by the foot on the travel side.
func _next_leg(axis: Vector3) -> Limb:
	if _last_leg == null or _time - _last_step_start > 0.8:
		return _legs[1] if _home(_legs[1]).dot(axis) > _home(_legs[0]).dot(axis) + 1e-4 else _legs[0]
	return _other_leg(_last_leg)


# --- Body pose ---------------------------------------------------------------

func _body_pose(delta: float) -> void:
	for i in B_COUNT:
		_q[i] = Quaternion.IDENTITY
	var sh := state.shuffle
	var walk := _walk_w
	var hang := smoothstep(0.0, 1.0, state.hang)
	var calm := (1.0 - walk) * (1.0 - hang)
	var forward_w := Vector3(_gb.basis.z.x, 0.0, _gb.basis.z.z).normalized()
	var lateral_w := Vector3(_gb.basis.x.x, 0.0, _gb.basis.x.z).normalized()
	var center := Vector3(_gb.origin.x, 0.0, _gb.origin.z)
	_gaze.update(delta, state.look, _look_goal(), _dir_goal(Vector3.BACK), state.is_focused(),
		state.is_talking(), walk > 0.5 and sh < 0.5, state.hang)

	# Gait signals: the swinging foot's progress and each foot's lead.
	var swing_leg: Limb = null
	var left_forward := 0.0
	var right_forward := 0.0
	for leg in _legs:
		if leg.swing >= 0.0:
			swing_leg = leg
		var lead := clampf((leg.pos - center).dot(forward_w) / (_step_len * 0.5), -1.0, 1.0) * (1.0 - hang)
		if leg.side > 0.0:
			left_forward = lead
		else:
			right_forward = lead
	var p := swing_leg.swing if swing_leg != null else 0.0

	# Pelvis: bob (highest mid-swing), sway over the stance foot, idle weight
	# shift, writing hip shift and squat; the slow part rides an underdamped
	# spring, so stopping settles with a small dip. Landing dips on a spring.
	var bob := 0.0
	var sway := 0.0
	if swing_leg != null:
		var amp := lerpf(BOB_WALK, BOB_SHUFFLE, sh) * walk + 0.003 * calm
		bob = (sin(PI * p) - 0.5) * amp * _leg_scale
		sway = (_other_leg(swing_leg).pos - center).dot(lateral_w) * lerpf(0.03, 0.1, sh) * maxf(walk, 0.4)
	sway += _shift * IDLE_SHIFT * _leg_scale * calm
	var slow := Vector3(
		sway + _hip_shift.dot(lateral_w),
		-(SOFT_KNEES + WALK_CROUCH * walk) * _leg_scale - _squat,
		_hip_shift.dot(forward_w)) * (1.0 - hang)
	_hips_offset = _pelvis_spring.step(slow, 11.0, 0.55, delta) + Vector3(0.0, bob, 0.0)
	if state.hang <= 0.0:
		_hips_offset.y -= _reach_drop()
	_hips_offset.y += _land_spring.step(0.0, 11.0, 0.5, delta)

	var yaw := -deg_to_rad(3.0) * (left_forward - right_forward) * walk * (1.0 - sh)
	var roll := _shift * deg_to_rad(2.5) * calm
	if swing_leg != null:
		roll -= swing_leg.side * deg_to_rad(0.6) * sin(PI * p) * walk
	_q[B_HIPS] = _rot(Vector3.UP, yaw) * _rot(_forward, roll) * _rot(_left, deg_to_rad(0.5) * walk)

	# Spine and chest: counter-rotation, lean with speed and into acceleration,
	# breathing, then the writing lean (a roll in the screen plane) and bend;
	# idle, now and then a slight 3/4 turn; held up, a hunch.
	var accel_forward := _accel.dot(forward_w)
	var accel_side := _accel.dot(lateral_w)
	var lean := deg_to_rad(0.4) * clampf(_speed, 0.0, 1.2) * (1.0 - sh) + clampf(accel_forward * 0.006, -0.025, 0.025)
	lean += deg_to_rad(6.0) * hang
	var side_lean := clampf(-accel_side * 0.01, -0.04, 0.04) - _shift * deg_to_rad(1.5) * calm
	var idle_twist := _idle_twist_spring.step(_gaze.twist, 2.2, 1.0, delta)
	_q[B_SPINE] = _rot(Vector3.UP, -yaw + idle_twist * 0.4) * _rot(_forward, -roll * 0.6 + side_lean) \
		* _rot(_left, lean + _breath * BREATH_CHEST * 0.4)
	if absf(_lean) > 1e-4 or absf(_bend) > 1e-4:
		_q[B_SPINE] = Quaternion(_screen_axis, -_lean) * _rot(_left, _bend) * _q[B_SPINE]
	_q[B_CHEST] = _rot(Vector3.UP, -yaw * 0.6 + _twist + idle_twist * 0.6) * _rot(_left, _breath * BREATH_CHEST * 0.6)
	_q[B_UPPER_CHEST] = _rot(_left, _breath * BREATH_CHEST * 0.4)
	_gesture_torso(delta)

	# Clavicles: breathing, the writing shoulder raise, the collar's shrug.
	var raise_left := _breath * BREATH_SHOULDER * 0.5 + HANG_SHRUG * hang
	var raise_right := raise_left
	if state.gesture == "write":
		if state.gesture_hand == AvatarState.Hand.LEFT:
			raise_left += _raise
		else:
			raise_right += _raise
	_q[B_L_SHOULDER] = _rot(_forward, raise_left)
	_q[B_R_SHOULDER] = _rot(_forward, -raise_right)

	# Arms: hang, swing against the opposite leg, forearm lags on a spring.
	# Held up they flail: wave about, or reach down for the floor; falling they
	# spread for balance, and come down with follow-through on landing.
	var flail := clampf(_hang_arms.step(state.hang, 10.0, 0.6, delta), -0.15, 1.0)
	for arm: Limb in _arms.values():
		var opposite := right_forward if arm.side > 0.0 else left_forward
		var swing := ARM_SWING * opposite * walk * (1.0 - sh) * clampf(_speed / 1.0, 0.5, 1.1)
		swing += deg_to_rad(1.5) * wobble(_time * 0.6, arm.side * 3.0 + 1.0) * calm
		var down := ARM_DOWN + deg_to_rad(1.2) * _breath + deg_to_rad(1.0) * wobble(_time * 0.4, arm.side * 5.0 + 2.0) \
			- deg_to_rad(4.0) * sh * walk + WALK_ARM_IN * walk * (1.0 - sh)
		var bend := ELBOW_BEND + WALK_ELBOW * walk * (1.0 - sh)
		if flail != 0.0:
			var f := state.fluster
			var ph := TAU * _flail_phase
			var wave := sin(ph + (0.0 if arm.side > 0.0 else 2.4))
			var wave2 := sin(ph * 0.53 + arm.side * 1.3)
			var low := 0.0 if state.airborne else 0.5 + 0.5 * wobble(_time * 0.35, 21.0 + arm.side)
			var f_down := lerpf(deg_to_rad(28.0) + deg_to_rad(16.0) * wave2 * f, deg_to_rad(58.0) + deg_to_rad(6.0) * wave, low)
			var f_swing := lerpf(deg_to_rad(10.0) + deg_to_rad(28.0) * wave * f, deg_to_rad(38.0) + deg_to_rad(10.0) * wave * f, low)
			var f_bend := lerpf(0.8 + 0.45 * wave2 * f, 0.3 + 0.15 * wave, low)
			if state.airborne or state.land_time >= 0.0:
				f_down = deg_to_rad(22.0)
				f_swing = deg_to_rad(12.0)
				f_bend = 0.35
			down = lerpf(down, f_down, flail)
			swing = lerpf(swing, f_swing, flail)
			bend = lerpf(bend, f_bend, flail)
		var lag := arm.elbow.step(swing, 9.0, 0.45, delta) - swing
		var flex := clampf(bend + ARM_LAG * lag, 0.05, 1.6)
		var wrist := WRIST_RELAX + deg_to_rad(2.0) * wobble(_time * 0.8, arm.side * 7.0 + 3.0)
		var upper_slot := B_L_UPPER_ARM if arm.side > 0.0 else B_R_UPPER_ARM
		_q[upper_slot] = _rot(_left, -swing) * _rot(_forward, -arm.side * down)
		_q[upper_slot + 2] = _rot(Vector3.UP, -arm.side * flex)
		_q[upper_slot + 4] = _rot(_forward, -arm.side * wrist)

	# Head: the gaze (eyes lead, the head follows part of the way on a spring),
	# nod (spring, rebounds) and tilt, stabilised against the torso so the gaze
	# stays steady; held up, it stays nearer upright than the swinging body.
	var goal := Vector3(clampf(_gaze.head.x, -LOOK_YAW_MAX, LOOK_YAW_MAX), clampf(_gaze.head.y, -LOOK_PITCH_DOWN, LOOK_PITCH_UP), 0.0)
	var look := _look_spring.step(goal, LOOK_OMEGA * (1.0 + 0.6 * hang), 0.85, delta)
	_look = Vector2(look.x, look.y)
	var eye_goal := Vector2(
		clampf(_gaze.eyes.x - _look.x, -EYE_YAW_MAX, EYE_YAW_MAX),
		clampf(_gaze.eyes.y - _look.y, -EYE_PITCH_MAX, EYE_PITCH_MAX))
	_eye = _eye.lerp(eye_goal, 1.0 - exp(-EYE_RATE * delta))
	var nod := _nod_spring.step(_nod_goal(), 20.0, 0.42, delta)
	var tilt := _tilt_spring.step(_gaze.tilt * maxf(1.0 - walk, hang) + deg_to_rad(1.0) * wobble(_time * 0.3, 11.0), 3.0 + 4.0 * hang, 1.0, delta)
	tilt -= _look.x * 0.08 + state.swing * 0.4 * hang
	var torso := _q[B_HIPS] * _q[B_SPINE] * _q[B_CHEST] * _q[B_UPPER_CHEST]
	var steady := Quaternion.IDENTITY.slerp(torso.inverse(), HEAD_STABILISE)
	var neck := NECK_SHARE if _slot_idx[B_NECK] >= 0 else 0.0
	var head := _yaw_pitch(_look * (1.0 - neck)) * _rot(_left, nod) * _rot(_forward, tilt)
	if neck > 0.0:
		_q[B_NECK] = steady * _yaw_pitch(_look * neck) * _rot(_left, nod * 0.25)
		_q[B_HEAD] = head
	else:
		_q[B_HEAD] = steady * head
	if _eye_bones:
		_q[B_L_EYE] = _yaw_pitch(_eye)
		_q[B_R_EYE] = _q[B_L_EYE]


## Torso and head accents that react to the gesturing arm.
func _gesture_torso(delta: float) -> void:
	var t := state.gesture_time
	var d := state.gesture_duration
	var twist := 0.0
	match state.gesture:
		"tap_desk":
			var e := envelope(t, d, 0.15, 0.2)
			var strike := 1.0 - (tap_offset(t, d).y - TAP_BASE.y) / TAP_LIFT
			_q[B_SPINE] = _rot(_left, deg_to_rad(7.0) * e + deg_to_rad(2.0) * strike * e) * _q[B_SPINE]
		"throw":
			var e := envelope(t, d, 0.12, 0.25)
			var phase := state.gesture_phase()
			var lean := smoothstep(0.38, 0.5, phase) * (1.0 - smoothstep(0.6, 1.0, phase))
			var back := smoothstep(0.1, 0.35, phase) * (1.0 - smoothstep(0.38, 0.46, phase))
			var chest := B_CHEST if _slot_idx[B_CHEST] >= 0 else B_SPINE
			_q[chest] = _rot(Vector3.UP, throw_twist(phase) * e) * _q[chest]
			_q[B_SPINE] = _rot(_left, (deg_to_rad(8.0) * lean - deg_to_rad(5.0) * back) * e) * _q[B_SPINE]
		"point":
			var arm: Limb = _arms.get(state.gesture_hand)
			if arm != null:
				twist = deg_to_rad(8.0) * arm.side * smoothstep(0.0, 1.0, arm.weight)
	_q[B_CHEST] = _rot(Vector3.UP, _gesture_twist.step(twist, 8.0, 0.6, delta)) * _q[B_CHEST]


func _nod_goal() -> float:
	var t := state.gesture_time
	var d := state.gesture_duration
	match state.gesture:
		"nod":
			return nod_angle(t, d)
		"tap_desk":
			return deg_to_rad(3.0) * (1.0 - (tap_offset(t, d).y - TAP_BASE.y) / TAP_LIFT) * envelope(t, d, 0.15, 0.2)
		"point":
			return deg_to_rad(4.0) * smoothstep(0.12, 0.3, t) * (1.0 - smoothstep(0.3, 0.6, t))
	return 0.0


## How far the hips must drop so both legs can reach their feet. A trailing
## planted foot first rises onto its toes (leg.heel, used by the leg IK).
func _reach_drop() -> float:
	var drop := 0.0
	var hips := _hips_rest_s + _c2s(_hips_offset) / _scale
	var forward_w := Vector3(_gb.basis.z.x, 0.0, _gb.basis.z.z).normalized()
	var rise := HEEL_RISE_MAX * _leg_scale
	for leg in _legs:
		var hip := _skel_xf * (hips + leg.hip_offset)
		var ankle := Vector3(leg.pos.x, _ground_y + leg.ankle + _foot_raise(leg), leg.pos.z)
		var d := hip - ankle
		var span := 0.996 * (leg.len_upper + leg.len_lower) * _scale
		var horizontal := Vector2(d.x, d.z).length()
		var reach := sqrt(maxf(span * span - horizontal * horizontal, 0.0))
		leg.need = d.y - reach
		if leg.swing >= 0.0:
			# A lifting-off foot just leaves the ground (toe-off); only a landing
			# foot pulls the pelvis down, gradually.
			drop = maxf(drop, leg.need * smoothstep(0.5, 1.0, leg.swing))
			continue
		var trailing := Vector3(d.x, 0.0, d.z).dot(forward_w) > 0.0
		drop = maxf(drop, leg.need - (rise if trailing else 0.0))
	for leg in _legs:
		leg.heel = clampf(leg.need - drop, 0.0, rise)
	return drop


## Unclamped (yaw toward the character's left, pitch up) to the commanded look
## target: the camera for USER, the point for POINT, straight ahead otherwise.
func _look_goal() -> Vector2:
	match state.look:
		AvatarState.Look.USER:
			return _dir_goal(Vector3.BACK)  # the orthographic camera looks down -Z
		AvatarState.Look.POINT:
			var head_idx := _slot_idx[B_HEAD]
			if head_idx < 0:
				return Vector2.ZERO
			var head := _skel_xf * _skeleton.get_bone_global_pose(head_idx).origin
			var p := state.look_point
			return _dir_goal(Vector3(p.x - head.x, p.y - head.y, LOOK_PLANE))
	return Vector2.ZERO


## (yaw toward the character's left, pitch up) of a world direction.
func _dir_goal(dir_world: Vector3) -> Vector2:
	var d := (_skel_inv.basis * dir_world).normalized()
	var fwd := d.dot(_forward)
	var lft := d.dot(_left)
	return Vector2(atan2(lft, fwd), atan2(d.y, Vector2(fwd, lft).length()))


func _apply_fk() -> void:
	if _hips >= 0:
		_skeleton.set_bone_pose_position(_hips, _hips_rest_pos + _hips_parent_inv * (_c2s(_hips_offset) / _scale))
	for i in B_COUNT:
		var idx := _slot_idx[i]
		if idx < 0 or ((i == B_L_EYE or i == B_R_EYE) and not _eye_bones):
			continue
		_skeleton.set_bone_pose_rotation(idx, _slot_rest_local[i] * (_slot_rest_global_inv[i] * _q[i] * _slot_rest_global[i]))


# --- Arms --------------------------------------------------------------------

func _update_arm(arm: Limb, delta: float) -> void:
	_arm_goal(arm)
	arm.goal_weight *= 1.0 - state.hang  # held up, the arms flail instead
	if arm.weight <= 0.0 and arm.goal_weight > 0.0:
		arm.target = arm.tip  # start from where the hand is
		arm.spring.reset(arm.tip)
	arm.weight = move_toward(arm.weight, arm.goal_weight, delta * arm.goal_rate)
	if arm.goal_weight > 0.0:
		match arm.goal_mode:
			1:
				arm.target = arm.target.lerp(arm.goal_target, 1.0 - exp(-IK_FOLLOW_RATE * delta))
			2:
				arm.target = arm.spring.step(arm.goal_target, POINT_OMEGA, POINT_ZETA, delta)
			_:
				arm.target = arm.goal_target
	arm.active = arm.weight > 0.0
	arm.hand_dir = Vector3.ZERO
	if not arm.active:
		return
	arm.w = smoothstep(0.0, 1.0, arm.weight)
	arm.aim = arm.target
	if state.gesture == "write" and state.gesture_hand == arm.hand:
		arm.hand_dir = _writing_wrist(arm, delta)


## Wrist while writing: the chalk trails the stroke a little and wiggles with
## the pen speed (the tip itself stays on the ik_target).
func _writing_wrist(arm: Limb, delta: float) -> Vector3:
	var v := _skel_inv.basis * state.ik_velocity
	var s := clampf(state.ik_velocity.length() / 0.35, 0.0, 1.0)
	var stroke := v.normalized() if v.length_squared() > 1e-10 else Vector3.ZERO
	var wiggle := stroke.cross(_forward) * (0.12 * sin(TAU * WRIST_WIGGLE_HZ * _time) * s)
	var want := (arm.fore_dir - stroke * (0.28 * s) + wiggle).normalized()
	if arm.dir.is_zero_approx():
		return want
	return arm.dir.lerp(want, 1.0 - exp(-14.0 * delta)).normalized()


## Fills arm.goal_* from the active gesture. No gesture on this hand = lower it.
func _arm_goal(arm: Limb) -> void:
	arm.goal_weight = 0.0
	arm.goal_mode = 0
	arm.goal_rate = 4.0
	if not state.is_hand_gesture() or state.gesture_hand != arm.hand:
		return
	var t := state.gesture_time
	var d := state.gesture_duration
	var base := _skeleton.get_bone_global_pose(arm.upper).origin
	match state.gesture:
		"write":
			arm.goal_weight = 1.0
			arm.goal_mode = 1
			arm.goal_target = _board_target(arm, base)
		"point":
			arm.goal_weight = 1.0
			arm.goal_mode = 2
			arm.goal_rate = 6.0
			if t < ANTICIPATION:
				arm.goal_target = base + _c2s(sided(Vector3(-0.1, -0.45, 0.35), arm.hand)) * arm.reach()
			else:
				arm.goal_target = _point_target(arm, base)
		"tap_desk":
			arm.goal_weight = envelope(t, d, 0.15, 0.2)
			arm.goal_rate = 10.0
			arm.goal_target = base + _c2s(sided(tap_offset(t, d), arm.hand)) * arm.reach()
		"throw":
			arm.goal_weight = envelope(t, d, 0.12, 0.25)
			arm.goal_rate = 12.0
			arm.goal_target = base + _c2s(sided(throw_offset(state.gesture_phase()), arm.hand)) * arm.reach()


## The ik_target on screen, placed in front of the shoulder so the hand never
## sinks into the body (the camera is orthographic: only x/y show on screen).
func _board_target(arm: Limb, base: Vector3) -> Vector3:
	if not state.has_ik_target:
		return base + _c2s(sided(WRITE_DEFAULT, arm.hand)) * arm.reach()
	var s := _skel_xf * base
	var reach := arm.reach() * _scale
	var t := state.ik_target
	var dxy := Vector2(t.x - s.x, t.y - s.y).length()
	var dz := sqrt(maxf(pow(reach * 0.92, 2.0) - dxy * dxy, 0.0))
	t.z = s.z + minf(dz, reach * WRITE_MAX_FORWARD)
	return _skel_inv * t


## A nearly straight arm from the shoulder toward point_target, slightly toward the viewer.
func _point_target(arm: Limb, base: Vector3) -> Vector3:
	var s := _skel_xf * base
	var p := state.point_target
	var d := Vector3(p.x - s.x, p.y - s.y, 0.0)
	if d.length() < 0.01:
		d = _skel_xf.basis * _c2s(sided(Vector3(-1.0, 0.3, 0.0), arm.hand))
		d.z = 0.0
	var dir := (d.normalized() * 0.9 + Vector3(0.0, 0.0, 0.35)).normalized()
	return _skel_inv * (s + dir * arm.reach() * _scale * POINT_REACH)


## Toe-down pitch of a foot: down a little as it leaves the ground, up
## (TOE_LAND) as the heel is set down, rolling flat over ROLL_TIME after landing.
func _foot_pitch(leg: Limb) -> float:
	if leg.swing >= 0.0:
		var swing_toe := TOE_SWING * sin(PI * pow(leg.swing, 0.7))
		return lerpf(swing_toe, TOE_LAND, smoothstep(0.55, 1.0, leg.swing)) * _walk_w
	if leg.planted_t < ROLL_TIME:
		return TOE_LAND * (1.0 - smoothstep(0.0, ROLL_TIME, leg.planted_t)) * _walk_w
	return 0.0


## Ankle height above its rest height: the step's lift, and enough for a
## pitched foot's toes (pitched down) or heel (pitched up) to just touch the ground.
func _foot_raise(leg: Limb) -> float:
	var pitch := _foot_pitch(leg)
	var contact := leg.foot_len * (sin(pitch) if pitch > 0.0 else HEEL_BACK * sin(-pitch))
	if leg.swing >= 0.0:
		return maxf(leg.lift * lift_curve(leg.swing), contact)
	return contact


func _setup_legs_ik() -> void:
	var hang := smoothstep(0.0, 1.0, state.hang)
	for leg in _legs:
		var ankle := Vector3(leg.pos.x, _ground_y + leg.ankle + _foot_raise(leg), leg.pos.z)
		var toe := _foot_pitch(leg)
		if leg.heel > 0.0 and leg.swing < 0.0:
			# Heel up, toes down: the foot pivots about its toes.
			ankle.y += leg.heel
			toe = asin(clampf((leg.foot_len * sin(toe) + leg.heel) / leg.foot_len, 0.0, 0.9))
		leg.aim = _skel_inv * ankle
		if hang > 0.0:
			# Dangling: small alternating back-kicks (the thigh stays near vertical,
			# the shank folds back), toes pointed; the legs trail the swing.
			var kick := AvatarBody.kick(_kick_phase, leg.side) * (0.3 + 0.7 * state.fluster)
			if state.airborne:
				kick *= 0.3  # reaching down for the floor
			var length := leg.len_upper + leg.len_lower
			var trail := clampf(-state.swing_velocity * 0.05, -0.08, 0.08) / _scale
			var dangle := _hips_rest_s + leg.hip_offset + Vector3.UP * (-length * (0.975 - 0.13 * kick)) \
				+ _forward * (length * (0.03 - 0.3 * kick)) + _left * (leg.side * length * 0.03 + trail)
			leg.aim = leg.aim.lerp(dangle, hang)
			toe = lerpf(toe, HANG_TOE + 0.3 * kick, hang)
		leg.reach_point = leg.aim
		leg.b = leg.len_lower
		var yaw := angle_difference(_body_yaw, leg.yaw)
		var turn := Quaternion(Vector3.UP, yaw)
		leg.pole = turn * _forward  # knees point where the (slightly toed-out) feet point
		leg.end_goal = turn * Quaternion(_left, toe) * leg.end_rest
		leg.active = true
		leg.w = 1.0


## Two-bone IK for every active limb, batched in phases so the skeleton
## recomputes global poses once per phase instead of once per bone.
func _solve_limbs() -> void:
	for limb in _limbs:
		if not limb.active or limb.is_leg:
			continue
		if limb.hand_dir == Vector3.ZERO:
			limb.reach_point = limb.aim
			limb.b = limb.len_lower + limb.len_tip
		else:
			limb.reach_point = limb.aim - limb.hand_dir * limb.len_tip
			limb.b = limb.len_lower
	# Phase 1: upper bones toward the elbow/knee.
	for limb in _limbs:
		if limb.active:
			var upper := _skeleton.get_bone_global_pose(limb.upper)
			limb.p_upper = upper.origin
			limb.q_upper = upper.basis.get_rotation_quaternion()
			limb.p_lower = _skeleton.get_bone_global_pose(limb.lower).origin
			limb.parent_xf = _skeleton.get_bone_global_pose(limb.parent) if limb.parent >= 0 else Transform3D.IDENTITY
			limb.q_parent = limb.parent_xf.basis.get_rotation_quaternion()
	for limb in _limbs:
		if not limb.active:
			continue
		var s := limb.p_upper
		var a := limb.len_upper
		var b := limb.b
		var to_target := limb.reach_point - s
		var dist := to_target.length()
		var dir := to_target / dist if dist > 1e-5 else _forward
		dist = clampf(dist, absf(a - b) + 1e-4, (a + b) * 0.999)
		var along := (a * a - b * b + dist * dist) / (2.0 * dist)
		var h := sqrt(maxf(a * a - along * along, 0.0))
		var pole := limb.pole if limb.is_leg else _c2s(sided(POLE, limb.hand))
		var bend := pole - dir * pole.dot(dir)
		if bend.length_squared() < 1e-8:
			bend = dir.cross(_left)
		var knee := s + dir * along + bend.normalized() * h
		limb.reach_point = s + dir * dist
		var global: Quaternion
		if limb.is_leg:
			limb.normal = dir.cross(bend).normalized()
			global = _aim(limb.rest_upper_q, limb.rest_upper_frame, knee - s, limb.normal)
		else:
			global = Quaternion((limb.p_lower - s).normalized(), (knee - s).normalized()) * limb.q_upper
		var local := limb.q_parent.inverse() * global
		_skeleton.set_bone_pose_rotation(limb.upper, _skeleton.get_bone_pose_rotation(limb.upper).slerp(local, limb.w))
	# Phase 2: lower bones toward the ankle/wrist/tip.
	for limb in _limbs:
		if limb.active:
			limb.thigh_xf = _skeleton.get_bone_global_pose(limb.upper)
			limb.q_upper = limb.thigh_xf.basis.get_rotation_quaternion()
			var lower := _skeleton.get_bone_global_pose(limb.lower)
			limb.p_lower = lower.origin
			limb.q_parent = lower.basis.get_rotation_quaternion()
			limb.p_end = _skeleton.get_bone_global_pose(limb.end).origin
	for limb in _limbs:
		if not limb.active:
			continue
		var global: Quaternion
		if limb.is_leg:
			global = _aim(limb.rest_lower_q, limb.rest_lower_frame, limb.reach_point - limb.p_lower, limb.normal)
		else:
			var arc := Quaternion((limb.p_end - limb.p_lower).normalized(), (limb.reach_point - limb.p_lower).normalized())
			global = arc * limb.q_parent
		var local := limb.q_upper.inverse() * global
		_skeleton.set_bone_pose_rotation(limb.lower, _skeleton.get_bone_pose_rotation(limb.lower).slerp(local, limb.w))
	# Phase 3: feet flat (yawed with the foot), hands straight or following hand_dir.
	for limb in _limbs:
		if limb.active:
			limb.q_upper = _skeleton.get_bone_global_pose(limb.lower).basis.get_rotation_quaternion()
			limb.q_parent = _skeleton.get_bone_global_pose(limb.end).basis.get_rotation_quaternion()
	for limb in _limbs:
		if not limb.active:
			continue
		var local: Quaternion
		if limb.is_leg:
			local = limb.q_upper.inverse() * limb.end_goal
		elif limb.hand_dir == Vector3.ZERO:
			local = limb.end_rest_local
		else:
			var arc := Quaternion((limb.q_parent * limb.tip_axis).normalized(), limb.hand_dir)
			local = limb.q_upper.inverse() * (arc * limb.q_parent)
		_skeleton.set_bone_pose_rotation(limb.end, _skeleton.get_bone_pose_rotation(limb.end).slerp(local, limb.w))
	# Phase 4: where the hands ended up.
	for arm: Limb in _arms.values():
		var elbow := _skeleton.get_bone_global_pose(arm.lower).origin
		var wrist := _skeleton.get_bone_global_pose(arm.end)
		arm.fore_dir = (wrist.origin - elbow).normalized()
		arm.dir = (wrist.basis.get_rotation_quaternion() * arm.tip_axis).normalized()
		arm.tip = wrist.origin + arm.dir * arm.len_tip


## Global rotation of a leg bone pointing along `dir` with its bend plane
## normal `normal`, built from the rest pose (rest_frame: rest direction and
## rest bend-plane normal, see _leg_frame), so the thigh never accumulates twist.
func _aim(rest_q: Quaternion, rest_frame: Basis, dir: Vector3, normal: Vector3) -> Quaternion:
	var d := dir.normalized()
	var n := (normal - d * normal.dot(d)).normalized()
	var to := Basis(d, n, d.cross(n))
	return (to * rest_frame.transposed()).get_rotation_quaternion() * rest_q


## Aiming frame of a bone at rest: its direction and the bend-plane normal of a
## leg bending forward (knee toward the character's front).
func _leg_frame(rest_dir: Vector3) -> Basis:
	var d := rest_dir.normalized()
	var n := d.cross(_forward).normalized()
	return Basis(d, n, d.cross(n))


## Thigh-parented skirt panels hang from the pelvis and follow the (solved)
## thigh only partly, so a stepping leg pushes the panel instead of splitting
## the skirt open; the spring chains below them start from there.
func _update_cloth() -> void:
	for c in _cloth:
		var thigh := c.leg.thigh_xf
		var by_thigh := thigh * c.rest_local
		var by_hips := c.leg.parent_xf * c.rel_hips
		var q := by_hips.basis.get_rotation_quaternion().slerp(by_thigh.basis.get_rotation_quaternion(), CLOTH_THIGH_FOLLOW)
		var local := thigh.affine_inverse() * Transform3D(Basis(q), by_hips.origin.lerp(by_thigh.origin, CLOTH_THIGH_FOLLOW))
		_skeleton.set_bone_pose_position(c.bone, local.origin)
		_skeleton.set_bone_pose_rotation(c.bone, local.basis.get_rotation_quaternion())


## Relaxed curl at rest, a grip while holding chalk, a fist with the index
## out while pointing, spread while flailing. Only rewritten when the curl changes.
func _update_fingers(delta: float) -> void:
	for arm: Limb in _arms.values():
		var h := 0 if arm.hand == AvatarState.Hand.RIGHT else 1
		if _finger_idx[h].is_empty():
			continue
		var curl := CURL_RELAXED
		var index := CURL_RELAXED
		if state.gesture_hand == arm.hand and arm.weight > 0.0:
			var w := smoothstep(0.0, 1.0, arm.weight)
			match state.gesture:
				"write":
					curl = lerpf(CURL_RELAXED, CURL_GRIP, w)
					index = lerpf(CURL_RELAXED, CURL_GRIP * 0.75, w)
				"point":
					curl = lerpf(CURL_RELAXED, CURL_FIST, w)
					index = lerpf(CURL_RELAXED, 0.03, w)
				"tap_desk", "throw":
					curl = lerpf(CURL_RELAXED, CURL_FIST * 0.9, w)
					index = curl
		if state.hang > 0.0:
			curl = lerpf(curl, 0.08, state.hang)
			index = lerpf(index, 0.08, state.hang)
		var c := arm.curl.step(curl, 16.0, 1.0, delta)
		var i := arm.index_curl.step(index, 16.0, 1.0, delta)
		if absf(c - arm.applied_curl) < 0.004 and absf(i - arm.applied_index) < 0.004:
			continue
		arm.applied_curl = c
		arm.applied_index = i
		var bones := _finger_idx[h]
		var kinds := _finger_kind[h]
		for k in bones.size():
			var finger := kinds[k] / 3
			var joint := kinds[k] % 3
			var amount := (i if finger == 0 else c) * FINGER_MAX[joint] * FINGER_SCALE[finger]
			var delta_q := _rot(_forward, -arm.side * amount)
			var rest_global: Quaternion = _finger_rest_global[h][k]
			_skeleton.set_bone_pose_rotation(bones[k], (_finger_rest_local[h][k] as Quaternion) * (rest_global.inverse() * delta_q * rest_global))


# --- Face --------------------------------------------------------------------

func _update_face(delta: float) -> void:
	if _expr.is_empty():
		return
	_fill_emotion_goal()
	for channel: String in CHANNELS:
		# Critically damped: expressions ease in and out.
		var value: float = _channels[channel]
		var velocity: float = _channel_vel[channel]
		var n := clampi(ceili(delta * 120.0), 1, 8)
		var step := delta / n
		for k in n:
			velocity += (EMOTION_OMEGA * EMOTION_OMEGA * (float(_emotion_goal[channel]) - value) - 2.0 * EMOTION_OMEGA * velocity) * step
			value += velocity * step
		_channels[channel] = value
		_channel_vel[channel] = velocity
	var talking := state.viseme_age <= VISEME_HOLD
	var k_mouth := 1.0 - exp(-VISEME_RATE * delta)
	for v: String in AvatarState.VISEMES:
		_mouth[v] = lerpf(_mouth[v], float(state.visemes[v]) if talking else 0.0, k_mouth)

	_blink_timer -= delta
	if _blink_timer <= 0.0:
		_blink_t = 0.0
		_blink_timer = next_blink_delay()
		_blink_speed = randf_range(0.85, 1.2)
	if _gaze.blink:
		# Gaze shifts come with a blink (unless one is already under way).
		_gaze.blink = false
		if _blink_t > 0.35:
			_blink_t = 0.0
			_blink_speed = randf_range(1.0, 1.25)
			_blink_timer = maxf(_blink_timer, 1.0)
	_blink_t += delta

	var allow_blink := 1.0
	var allow_mouth := 1.0
	for e: String in EMOTIONS:
		var w: float = _channels[e]
		allow_blink *= _override_factor(_override_blink.get(e, "blend" if e == "happy" else "none"), w)
		allow_mouth *= _override_factor(_override_mouth.get(e, "none"), w)

	for key: String in WEIGHT_KEYS:
		_weights[key] = 0.0
	for e: String in EMOTIONS:
		_weights[e] = clampf(_channels[e], 0.0, 1.0)
	# Soft lids (never a wide-open stare), lower when looking down; not while
	# surprised, smiling or angry.
	var open_face := clampf(_channels["surprised"] + _channels["happy"] + _channels["angry"], 0.0, 1.0)
	var lid := _gaze.lid * (1.0 - open_face)
	var eyes := maxf(_channels["eyes_closed"], maxf(blink_curve(_blink_t, _blink_speed), lid) * allow_blink)
	if _expr.has("blink"):
		_weights["blink"] = eyes
	else:
		_weights["blinkleft"] = eyes
		_weights["blinkright"] = eyes
	for v: String in AvatarState.VISEMES:
		_weights[v] = _mouth[v] * allow_mouth
	_weights["oh"] = maxf(_weights["oh"], _channels["surprised_mouth"])
	if state.grabbed:
		# Flustered "wawawa": the mouth flaps a little while she is held up.
		var flap := state.hang * state.fluster * (0.14 + 0.1 * sin(TAU * 4.3 * _time))
		_weights["aa"] = maxf(_weights["aa"], flap * allow_mouth)
	if not _eye_bones:
		# Blend-shape eyes (VRM lookAt type BlendShape): left = the avatar's own left.
		_weights["lookleft"] = clampf(_eye.x / EYE_YAW_MAX, 0.0, 1.0)
		_weights["lookright"] = clampf(-_eye.x / EYE_YAW_MAX, 0.0, 1.0)
		_weights["lookup"] = clampf(_eye.y / EYE_PITCH_MAX, 0.0, 1.0)
		_weights["lookdown"] = clampf(-_eye.y / EYE_PITCH_MAX, 0.0, 1.0)
	_write_shapes(_weights)


func _fill_emotion_goal() -> void:
	for channel: String in CHANNELS:
		_emotion_goal[channel] = 0.0
	var w := state.emotion_weight
	match state.emotion:
		"happy":
			_emotion_goal["happy"] = w
		"angry":
			_emotion_goal["angry"] = w
		"surprised":
			if _expr.has("surprised"):
				_emotion_goal["surprised"] = w
			else:
				_emotion_goal["surprised_mouth"] = 0.5 * w
		"sleepy":
			_emotion_goal["eyes_closed"] = 0.6 * w
			_emotion_goal["relaxed" if _expr.has("relaxed") else "sad"] = 0.3 * w
	# Relieved for a moment after landing on her feet.
	var relief := smoothstep(0.1, 0.35, _relief_t) * (1.0 - smoothstep(1.3, 2.0, _relief_t))
	if relief > 0.0:
		var key := "relaxed" if _expr.has("relaxed") else "happy"
		_emotion_goal[key] = maxf(_emotion_goal[key], (0.6 if key == "relaxed" else 0.35) * relief)


static func _override_factor(mode: String, weight: float) -> float:
	match mode:
		"block":
			return 1.0 - clampf(weight * 4.0, 0.0, 1.0)
		"blend":
			return 1.0 - clampf(weight, 0.0, 1.0)
	return 1.0


func _write_shapes(weights: Dictionary) -> void:
	for acc: Array in _slot_acc:
		acc.fill(0.0)
	for expression: String in weights:
		var w: float = weights[expression]
		if w <= 0.0001 or not _expr.has(expression):
			continue
		for bind: Array in _expr[expression]:
			var acc: Array = _slot_acc[bind[0]]
			acc[bind[1]] += w * float(bind[2])
	for i in _slots.size():
		var mesh := _slots[i]
		var acc: Array = _slot_acc[i]
		var last: Array = _slot_last[i]
		for idx in _slot_used[i]:
			var v := clampf(acc[idx], 0.0, SHAPE_MAX)
			if absf(v - float(last[idx])) > 0.0005:
				mesh.set_blend_shape_value(idx, v)
				last[idx] = v


## Effective weight of an expression as seen through its first blend shape
## bind (the written value divided by the bind weight); -1 if unknown. Tests.
func expression_value(expression: String) -> float:
	var binds: Array = _expr.get(expression.to_lower(), [])
	if binds.is_empty():
		return -1.0
	var bind: Array = binds[0]
	return _slots[bind[0]].get_blend_shape_value(bind[1]) / maxf(float(bind[2]), 0.001)


## Reads expression -> blend shape binds from godot-vrm's AnimationPlayer. Both
## VRM 0.x (presets renamed to 1.0 names: joy->happy, a->aa, ...) and VRM 1.0
## produce one single-key animation per expression with blend shape tracks.
## Material-bound expressions are ignored.
func _setup_expressions(avatar: Node) -> void:
	var player := avatar.get_node_or_null("AnimationPlayer") as AnimationPlayer
	if player == null:
		return
	var root := player.get_node_or_null(player.root_node)
	if root == null:
		root = avatar
	for anim_name: StringName in player.get_animation_list():
		var key := String(anim_name).to_lower()
		if key == "reset" or (key.begins_with("look") and key.ends_with("raw")):
			continue
		var anim := player.get_animation(anim_name)
		var binds: Array = []
		for track in anim.get_track_count():
			if anim.track_get_type(track) != Animation.TYPE_BLEND_SHAPE or anim.track_get_key_count(track) == 0:
				continue
			var path := anim.track_get_path(track)
			var mesh := root.get_node_or_null(NodePath(path.get_concatenated_names())) as MeshInstance3D
			if mesh == null:
				continue
			var shape := mesh.find_blend_shape_by_name(StringName(path.get_concatenated_subnames()))
			if shape < 0:
				continue
			var slot := _mesh_slot(mesh)
			if not _slot_used[slot].has(shape):
				_slot_used[slot].append(shape)
			binds.append([slot, shape, float(anim.track_get_key_value(track, 0))])
		if binds.is_empty():
			continue
		_expr[key] = binds
		# VRM 1.0 only: "none" | "block" | "blend" (VRM 0.x has no overrides).
		for pair: Array in [["vrm_override_blink", _override_blink], ["vrm_override_mouth", _override_mouth]]:
			if anim.has_meta(pair[0]) and anim.get_meta(pair[0]) is String:
				(pair[1] as Dictionary)[key] = anim.get_meta(pair[0])
	_eye_bones = _bones.has("LeftEye") and _bones.has("RightEye") and not _expr.has("lookleft")


func _mesh_slot(mesh: MeshInstance3D) -> int:
	var slot := _slots.find(mesh)
	if slot >= 0:
		return slot
	_slots.append(mesh)
	_slot_used.append(PackedInt32Array())
	var count := mesh.get_blend_shape_count()
	var acc: Array = []
	acc.resize(count)
	acc.fill(0.0)
	var last: Array = []
	last.resize(count)
	last.fill(-1.0)  # forces the first write
	_slot_acc.append(acc)
	_slot_last.append(last)
	return _slots.size() - 1


# --- Setup helpers -----------------------------------------------------------

## Concatenates the surfaces of a mesh that share an opaque/cutout material, so
## the result draws and skins in one pass per material. The Compatibility
## renderer re-skins every surface with its own GPU pass each frame the skeleton
## moves; on WebGL each pass is expensive (Tsukuyomi's hair: 78 surfaces, 6
## materials). Meshes with blend shapes and transparent surfaces (draw order
## matters) are left alone. Returns the number of surfaces removed.
static func merge_surfaces(mesh_instance: MeshInstance3D) -> int:
	var mesh := mesh_instance.mesh as ArrayMesh
	if mesh == null or mesh.get_blend_shape_count() > 0 or mesh.get_surface_count() < 2:
		return 0
	var array_bits := (1 << Mesh.ARRAY_MAX) - 1
	var keep_flags := Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS
	for i in 4:
		keep_flags |= Mesh.ARRAY_FORMAT_CUSTOM_MASK << (Mesh.ARRAY_FORMAT_CUSTOM_BASE + i * Mesh.ARRAY_FORMAT_CUSTOM_BITS)
	var groups: Array[Dictionary] = []
	var by_key: Dictionary = {}
	for s in mesh.get_surface_count():
		var material := mesh_instance.get_active_material(s)
		var format := mesh.surface_get_format(s)
		var key := "solo:%d" % s
		var mergeable := material != null and not _is_transparent(material) \
			and mesh.surface_get_primitive_type(s) == Mesh.PRIMITIVE_TRIANGLES \
			and (format & Mesh.ARRAY_FORMAT_INDEX) != 0
		if mergeable:
			key = "%d:%d:%d" % [material.get_instance_id(), format & array_bits, format & keep_flags]
		if not by_key.has(key):
			by_key[key] = groups.size()
			groups.append({"material": material, "flags": format & keep_flags, "surfaces": []})
		(groups[by_key[key]].surfaces as Array).append(s)
	if groups.size() == mesh.get_surface_count():
		return 0
	var merged := ArrayMesh.new()
	merged.resource_name = mesh.resource_name
	merged.custom_aabb = mesh.custom_aabb
	for group in groups:
		var arrays: Array = []
		arrays.resize(Mesh.ARRAY_MAX)
		var vertex_count := 0
		for s: int in group.surfaces:
			var part := mesh.surface_get_arrays(s)
			for a in Mesh.ARRAY_MAX:
				if part[a] == null:
					continue
				var data: Variant = part[a]
				if a == Mesh.ARRAY_INDEX and vertex_count > 0:
					var indices := PackedInt32Array(data)
					for i in indices.size():
						indices[i] += vertex_count
					data = indices
				arrays[a] = data if arrays[a] == null else arrays[a] + data
			vertex_count += (part[Mesh.ARRAY_VERTEX] as PackedVector3Array).size()
		merged.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays, [], {}, group.flags)
		merged.surface_set_material(merged.get_surface_count() - 1, group.material)
	mesh_instance.mesh = merged
	return mesh.get_surface_count() - merged.get_surface_count()


## Alpha-blended materials must keep their surface order; cutout ones need not.
## MToon (Godot-MToon-Shader) names its blended variants mtoon_trans*.
static func _is_transparent(material: Material) -> bool:
	if material is BaseMaterial3D:
		var transparency := (material as BaseMaterial3D).transparency
		return transparency == BaseMaterial3D.TRANSPARENCY_ALPHA \
			or transparency == BaseMaterial3D.TRANSPARENCY_ALPHA_DEPTH_PRE_PASS
	if material is ShaderMaterial and (material as ShaderMaterial).shader != null:
		var shader := (material as ShaderMaterial).shader
		var file := shader.resource_path.get_file()
		if file.begins_with("mtoon"):
			return file.contains("trans")
		return shader.code.contains("ALPHA") and not shader.code.contains("ALPHA_SCISSOR")
	return true


func _yaw_pitch(v: Vector2) -> Quaternion:
	return _rot(Vector3.UP, v.x) * _rot(_left, -v.y)


func _rot(axis: Vector3, angle: float) -> Quaternion:
	return Quaternion(axis.normalized(), angle)


## Character space (x = left, y = up, z = forward) to skeleton space.
func _c2s(v: Vector3) -> Vector3:
	return _left * v.x + Vector3.UP * v.y + _forward * v.z


func _find_skeleton(node: Node) -> Skeleton3D:
	if node is Skeleton3D:
		return node
	for child in node.get_children():
		var found := _find_skeleton(child)
		if found != null:
			return found
	return null


## Humanoid profile names first (godot-vrm renames bones), then the original
## names recorded in the VRM bone map.
func _find_humanoid(bone_map: BoneMap, bone: String) -> int:
	var idx := _skeleton.find_bone(bone)
	if idx < 0 and bone_map != null:
		var original := bone_map.get_skeleton_bone_name(bone)
		if original != StringName():
			idx = _skeleton.find_bone(original)
	if idx >= 0:
		_bones[bone] = idx
		_rest_local[idx] = _skeleton.get_bone_rest(idx).basis.get_rotation_quaternion()
		_rest_global[idx] = _skeleton.get_bone_global_rest(idx).basis.get_rotation_quaternion()
	return idx


func _map_bones(meta: Resource) -> void:
	var bone_map: BoneMap = meta.get("humanoid_bone_mapping") if meta != null else null
	_slot_idx.resize(B_COUNT)
	_slot_rest_local.resize(B_COUNT)
	_slot_rest_global.resize(B_COUNT)
	_slot_rest_global_inv.resize(B_COUNT)
	for i in B_COUNT:
		var idx := _find_humanoid(bone_map, SLOT_BONES[i])
		_slot_idx[i] = idx
		var local := _skeleton.get_bone_rest(idx).basis.get_rotation_quaternion() if idx >= 0 else Quaternion.IDENTITY
		var global := _skeleton.get_bone_global_rest(idx).basis.get_rotation_quaternion() if idx >= 0 else Quaternion.IDENTITY
		_slot_rest_local[i] = local
		_slot_rest_global[i] = global
		_slot_rest_global_inv[i] = global.inverse()
	for bone: String in LIMB_BONES:
		_find_humanoid(bone_map, bone)
	for side: String in ["Left", "Right"]:
		for finger: String in FINGERS:
			for joint: String in FINGER_JOINTS:
				_find_humanoid(bone_map, side + finger + joint)


func _setup_limbs() -> void:
	var skel_to_body := global_transform.affine_inverse() * _skeleton.global_transform
	_hips = _slot_idx[B_HIPS]
	if _hips >= 0:
		_hips_rest_pos = _skeleton.get_bone_rest(_hips).origin
		_hips_rest_s = _skeleton.get_bone_global_rest(_hips).origin
		var parent := _skeleton.get_bone_parent(_hips)
		_hips_parent_inv = _skeleton.get_bone_global_rest(parent).basis.inverse() if parent >= 0 else Basis.IDENTITY
	var scale := _skeleton.global_transform.basis.get_scale().x
	for hand: AvatarState.Hand in [AvatarState.Hand.RIGHT, AvatarState.Hand.LEFT]:
		var side := "Right" if hand == AvatarState.Hand.RIGHT else "Left"
		var arm := Limb.new()
		arm.hand = hand
		arm.side = -1.0 if hand == AvatarState.Hand.RIGHT else 1.0
		arm.upper = _bones.get(side + "UpperArm", -1)
		arm.lower = _bones.get(side + "LowerArm", -1)
		arm.end = _bones.get(side + "Hand", -1)
		if arm.upper < 0 or arm.lower < 0 or arm.end < 0:
			continue
		arm.parent = _skeleton.get_bone_parent(arm.upper)
		var s := _skeleton.get_bone_global_rest(arm.upper).origin
		var e := _skeleton.get_bone_global_rest(arm.lower).origin
		var w := _skeleton.get_bone_global_rest(arm.end).origin
		arm.len_upper = s.distance_to(e)
		arm.len_lower = e.distance_to(w)
		if arm.len_upper < 1e-4 or arm.len_lower < 1e-4:
			continue
		arm.end_rest = _skeleton.get_bone_global_rest(arm.end).basis.get_rotation_quaternion()
		arm.end_rest_local = _skeleton.get_bone_rest(arm.end).basis.get_rotation_quaternion()
		var middle: int = _bones.get(side + "MiddleProximal", -1)
		if middle >= 0:
			arm.len_tip = w.distance_to(_skeleton.get_bone_global_rest(middle).origin)
			arm.tip_axis = _skeleton.get_bone_rest(middle).origin.normalized()
		else:
			arm.len_tip = arm.len_lower * 0.3
			arm.tip_axis = (arm.end_rest.inverse() * (w - e)).normalized()
		arm.len_tip += CHALK_TIP / maxf(scale, 1e-4)
		arm.rest_body = skel_to_body * s
		arm.dir = (w - e).normalized()
		arm.fore_dir = arm.dir
		arm.tip = w + arm.dir * arm.len_tip
		arm.curl.reset(CURL_RELAXED)
		arm.index_curl.reset(CURL_RELAXED)
		_arms[hand] = arm
		_limbs.append(arm)
		var spine := _slot_idx[B_SPINE]
		if spine >= 0:
			_lean_lever = maxf(_skeleton.get_bone_global_rest(spine).origin.distance_to(s) * scale, 0.1)
	var leg_length := 0.0
	for side: String in ["Left", "Right"]:
		var leg := Limb.new()
		leg.is_leg = true
		leg.side = 1.0 if side == "Left" else -1.0
		leg.upper = _bones.get(side + "UpperLeg", -1)
		leg.lower = _bones.get(side + "LowerLeg", -1)
		leg.end = _bones.get(side + "Foot", -1)
		if leg.upper < 0 or leg.lower < 0 or leg.end < 0 or _hips < 0:
			continue
		leg.parent = _skeleton.get_bone_parent(leg.upper)
		var hip := _skeleton.get_bone_global_rest(leg.upper).origin
		var knee := _skeleton.get_bone_global_rest(leg.lower).origin
		var ankle := _skeleton.get_bone_global_rest(leg.end).origin
		leg.len_upper = hip.distance_to(knee)
		leg.len_lower = knee.distance_to(ankle)
		leg.hip_offset = hip - _hips_rest_s
		leg.end_rest = _skeleton.get_bone_global_rest(leg.end).basis.get_rotation_quaternion()
		leg.rest_upper_q = _skeleton.get_bone_global_rest(leg.upper).basis.get_rotation_quaternion()
		leg.rest_lower_q = _skeleton.get_bone_global_rest(leg.lower).basis.get_rotation_quaternion()
		leg.rest_upper_frame = _leg_frame(knee - hip)
		leg.rest_lower_frame = _leg_frame(ankle - knee)
		var foot_body := skel_to_body * ankle
		var hip_body := skel_to_body * hip
		leg.ankle = foot_body.y
		var toes: int = _bones.get(side + "Toes", -1)
		if toes >= 0:
			leg.foot_len = maxf(ankle.distance_to(_skeleton.get_bone_global_rest(toes).origin) * scale, 0.03)
		else:
			leg.foot_len = (leg.len_upper + leg.len_lower) * scale * 0.2
		# Standing, the feet are about hip-width apart (the legs straight down,
		# not converging inward), toes slightly out.
		var width := maxf(maxf(absf(foot_body.x), absf(hip_body.x) * STANCE_WIDTH), 0.06)
		leg.rest_body = Vector3((signf(foot_body.x) if absf(foot_body.x) > 1e-4 else leg.side) * width, 0.0, foot_body.z)
		leg_length = maxf(leg_length, (leg.len_upper + leg.len_lower) * scale)
		_legs.append(leg)
		_limbs.append(leg)
	if _legs.size() != 2:
		_legs.clear()
		for i in range(_limbs.size() - 1, -1, -1):
			if _limbs[i].is_leg:
				_limbs.remove_at(i)
	_leg_scale = leg_length / REF_LEG if leg_length > 0.0 else 1.0
	# Held up by the collar: the nape (the neck bone's root).
	var nape := _slot_idx[B_NECK] if _slot_idx[B_NECK] >= 0 else _slot_idx[B_HEAD]
	if nape >= 0:
		_grab_height = (skel_to_body * _skeleton.get_bone_global_rest(nape).origin).y


func _setup_fingers() -> void:
	for h in 2:
		var side := "Right" if h == 0 else "Left"
		for f in FINGERS.size():
			for j in FINGER_JOINTS.size():
				var idx: int = _bones.get(side + FINGERS[f] + FINGER_JOINTS[j], -1)
				if idx < 0:
					continue
				_finger_idx[h].append(idx)
				_finger_kind[h].append(f * 3 + j)
				_finger_rest_local[h].append(_rest_local[idx])
				_finger_rest_global[h].append(_rest_global[idx])


## Spring chains (VRM secondary animation) hanging from a thigh get their root
## re-hung from the pelvis each frame (_update_cloth): VRoid rigs the front and
## back skirt panels to the upper legs, so a stepping leg split the skirt open.
## Skirt-like chains without thigh colliders get some (_ensure_leg_colliders).
func _setup_cloth(avatar: Node) -> void:
	if _legs.size() != 2:
		return
	var humanoid: Dictionary = {}
	for idx: int in _bones.values():
		humanoid[idx] = true
	for node: Node in avatar.find_children("*", "Node3D", true, false):
		var chains: Variant = node.get("spring_bones")
		if not chains is Array:
			continue
		for chain: Variant in chains:
			var root := _chain_root(chain)
			if root < 0:
				continue
			# The bone just below the first humanoid ancestor.
			var child := root
			var parent := _skeleton.get_bone_parent(child)
			while parent >= 0 and not humanoid.has(parent):
				child = parent
				parent = _skeleton.get_bone_parent(child)
			for leg in _legs:
				if parent != leg.upper or leg.parent < 0:
					continue
				var known := false
				for c in _cloth:
					known = known or c.bone == child
				if known:
					continue
				var cloth := Cloth.new()
				cloth.bone = child
				cloth.leg = leg
				cloth.rest_local = _skeleton.get_bone_rest(child)
				cloth.rel_hips = _skeleton.get_bone_global_rest(leg.parent).affine_inverse() * _skeleton.get_bone_global_rest(child)
				_cloth.append(cloth)
		_ensure_leg_colliders(node)


func _chain_root(chain: Variant) -> int:
	if chain == null or not chain is Resource:
		return -1
	var joints: Variant = (chain as Resource).get("joint_nodes")
	if not joints is PackedStringArray or (joints as PackedStringArray).is_empty():
		return -1
	return _skeleton.find_bone((joints as PackedStringArray)[0])


## Skirt-like spring chains (rooted at the pelvis or a thigh, hanging below the
## hips) that have no collider on the thighs get capsules sized from the leg
## bones, so a stepping leg pushes the skirt out instead of passing through it.
## The imported chain resources are never modified: changed chains are copies.
## force: add them even where thigh colliders exist (tests). Returns the count.
func _ensure_leg_colliders(secondary: Node, force := false) -> int:
	var chains: Variant = secondary.get("spring_bones")
	if not chains is Array or _legs.size() != 2 or _hips < 0:
		return 0
	var hips_y := _skeleton.get_bone_global_rest(_hips).origin.y
	var group: VRMColliderGroup = null
	var fresh: Array[VRMSpringBone] = []
	var changed := 0
	for chain: Variant in chains:
		var spring := chain as VRMSpringBone
		fresh.append(spring)
		var root := _chain_root(spring)
		if root < 0:
			continue
		var anchor := _skeleton.get_bone_parent(root)
		while anchor >= 0 and not (anchor == _hips or anchor == _legs[0].upper or anchor == _legs[1].upper):
			if _bones.values().has(anchor):
				anchor = -1  # rooted at some other humanoid bone (hair, chest, ...)
				break
			anchor = _skeleton.get_bone_parent(anchor)
		var joints := spring.joint_nodes
		var tip := _skeleton.find_bone(joints[joints.size() - 1]) if not joints[joints.size() - 1].is_empty() else -1
		if tip < 0 and joints.size() >= 2:
			tip = _skeleton.find_bone(joints[joints.size() - 2])
		if anchor < 0 or tip < 0:
			continue
		var top := _skeleton.get_bone_global_rest(root).origin.y
		var bottom := _skeleton.get_bone_global_rest(tip).origin.y
		if bottom > top - 0.02 or bottom > hips_y:
			continue  # not hanging down past the hips
		if not force and _has_thigh_collider(spring):
			continue
		if group == null:
			group = _leg_collider_group()
		var copy := spring.duplicate() as VRMSpringBone
		var groups: Array[VRMColliderGroup] = []
		groups.assign(spring.collider_groups)
		groups.append(group)
		copy.collider_groups = groups
		fresh[fresh.size() - 1] = copy
		changed += 1
	if changed > 0:
		secondary.set("spring_bones", fresh)  # the secondary rebuilds its runtime next tick
	return changed


func _has_thigh_collider(spring: VRMSpringBone) -> bool:
	for group in spring.collider_groups:
		if group == null:
			continue
		for collider in group.colliders:
			if collider == null or collider.bone.is_empty():
				continue
			var bone := _skeleton.find_bone(collider.bone)
			for leg in _legs:
				if bone == leg.upper and collider.radius >= leg.len_upper * 0.15:
					return true
	return false


## Capsules from hip to knee plus a knee sphere, per leg (skeleton units).
func _leg_collider_group() -> VRMColliderGroup:
	var group := VRMColliderGroup.new()
	group.resource_name = "studymate_legs"
	var colliders: Array[VRMCollider] = []
	for leg in _legs:
		var thigh := VRMCollider.new()
		thigh.bone = _skeleton.get_bone_name(leg.upper)
		thigh.is_capsule = true
		thigh.tail = _skeleton.get_bone_rest(leg.lower).origin
		thigh.radius = leg.len_upper * 0.27
		colliders.append(thigh)
		var knee := VRMCollider.new()
		knee.bone = _skeleton.get_bone_name(leg.lower)
		knee.radius = leg.len_upper * 0.21
		colliders.append(knee)
	group.colliders = colliders
	return group


## Derives forward/left from the rest pose and turns the avatar to face +Z.
func _detect_orientation(avatar: Node3D) -> void:
	var l: int = _bones.get("LeftUpperArm", -1)
	var r: int = _bones.get("RightUpperArm", -1)
	if l < 0 or r < 0:
		return
	var left := _skeleton.get_bone_global_rest(l).origin - _skeleton.get_bone_global_rest(r).origin
	left.y = 0.0
	if left.length() < 0.001:
		return
	_left = left.normalized()
	_forward = _left.cross(Vector3.UP).normalized()
	var forward_here := (global_transform.basis.inverse() * _skeleton.global_transform.basis * _forward)
	if forward_here.z < 0.0:
		avatar.rotate_y(PI)


## Scales the avatar to BODY_HEIGHT and puts its feet at the origin.
func _normalize(avatar: Node3D) -> void:
	var box := _mesh_bounds(avatar, Transform3D.IDENTITY)
	if box.size.y <= 0.001:
		return
	var k := BODY_HEIGHT / box.size.y
	avatar.scale *= k
	avatar.position = Vector3(-(box.position.x + box.size.x / 2.0) * k, -box.position.y * k, 0.0) \
		+ avatar.position * k
	# T-pose arms inflate the width; arms are lowered at runtime, so cap it.
	var half_width := minf(box.size.x * k / 2.0, BODY_HEIGHT * 0.22)
	var half_depth := minf(box.size.z * k / 2.0, BODY_HEIGHT * 0.2)
	_bounds = AABB(Vector3(-half_width, 0.0, -half_depth), Vector3(half_width * 2.0, BODY_HEIGHT, half_depth * 2.0))
	_base_y = position.y


func _mesh_bounds(node: Node, xform: Transform3D) -> AABB:
	var result := AABB()
	var has := false
	var here := xform
	if node is Node3D:
		here = xform * (node as Node3D).transform
	if node is MeshInstance3D and (node as MeshInstance3D).mesh != null:
		result = here * (node as MeshInstance3D).get_aabb()
		has = true
	for child in node.get_children():
		var child_box := _mesh_bounds(child, here)
		if child_box.size == Vector3.ZERO:
			continue
		result = result.merge(child_box) if has else child_box
		has = true
	return result
