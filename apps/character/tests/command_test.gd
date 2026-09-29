extends SceneTree
## Headless command suite. Boots the main scene, drives every Director -> Godot
## command through the Bridge test hook (_bridge.inject / _bridge.sent) and checks
## the reported events and the resulting pose/face (gesture, gaze life, gait
## limits, grab/release), on:
##   - the default avatar (res://avatars/tsukuyomi-a.vrm, editor-imported)
##   - a runtime-loaded VRM 0.x (models/test/Godette_vrm_v4.vrm) and any extra
##     .vrm paths passed after --
##   - the procedural placeholder body.
## Usage (from the repo root):
##   godot --headless --path apps/character --fixed-fps 60 --script res://tests/command_test.gd [-- extra.vrm ...]
## Exit code 0 = all checks passed.

const GODETTE := "../../models/test/Godette_vrm_v4.vrm"
const IK_TOLERANCE_CSS := 4.0

var _main: Node
var _bridge: Node  # the Bridge autoload (not resolvable at compile time under --script)
var _character: Character
var _clock := 0.0
var _checks := 0
var _failures: Array[String] = []
var _label := ""


func _initialize() -> void:
	_run()


func _process(delta: float) -> bool:
	_clock += delta
	return false


func _run() -> void:
	seed(20260926)  # gaze and idle life are randomised; keep runs repeatable
	_bridge = root.get_node("Bridge")
	_main = (load("res://scenes/main.tscn") as PackedScene).instantiate()
	# Headless windows are 64x64; host the scene in a desktop-sized viewport.
	var viewport := SubViewport.new()
	viewport.size = Vector2i(1280, 720)
	root.add_child(viewport)
	viewport.add_child(_main)
	await process_frame  # main._ready runs once the tree starts
	_main.set("frame_cap_enabled", false)
	Engine.max_fps = 0
	_character = _main.get_node("Character")
	await _wait(0.1)

	_label = "startup"
	_check(_first("ready") != null, "ready sent")
	var loaded: Variant = _first("avatar_loaded")
	_check(loaded != null and loaded.id == "default", "avatar_loaded(default) sent at startup")
	var has_default := ResourceLoader.exists(Character.DEFAULT_AVATAR)
	if has_default:
		_check(_character.body() is VrmBody, "default avatar is a VrmBody")
		_check(str(loaded.meta.title).length() > 0, "default avatar meta has a title")
	else:
		push_warning("default avatar not imported; run tools/prepare_assets.py")

	var suites: Array = []
	if has_default:
		suites.append(["tsukuyomi (imported)", {"type": "load_avatar", "id": "default"}])
	var godette := ProjectSettings.globalize_path("res://").path_join(GODETTE).simplify_path()
	if FileAccess.file_exists(godette):
		suites.append(["godette (runtime)", {"type": "load_avatar", "id": "godette", "path": godette}])
	for extra: String in OS.get_cmdline_user_args():
		suites.append([extra.get_file(), {"type": "load_avatar", "id": "extra", "path": extra}])
	suites.append(["placeholder", {"type": "load_avatar", "id": "placeholder"}])
	for suite: Array in suites:
		await _suite(suite[0], suite[1])

	_label = "avatar errors"
	_bridge.sent.clear()
	_bridge.inject({"type": "load_avatar", "id": "missing", "path": "user://nope.vrm"})
	_bridge.inject({"type": "load_avatar", "id": "nopath"})
	await _wait(0.05)
	_check(_count("avatar_error") == 2, "bad load_avatar -> avatar_error x2")
	if has_default:
		_bridge.inject({"type": "load_avatar", "id": "by-path", "path": Character.DEFAULT_AVATAR})
		await _wait(0.05)
		var by_path: Variant = _last("avatar_loaded")
		_check(by_path != null and by_path.id == "by-path" and _character.body() is VrmBody, "load_avatar with an imported res:// path")

	_blink_timing_test()
	await _frame_cap_test()

	print("\n%d checks, %d failed" % [_checks, _failures.size()])
	for f in _failures:
		printerr("FAIL: ", f)
	print("OK" if _failures.is_empty() else "FAILED")
	quit(0 if _failures.is_empty() else 1)


func _suite(label: String, load_cmd: Dictionary) -> void:
	_label = label
	print("\n== ", label)
	_bridge.sent.clear()
	_bridge.inject(load_cmd)
	await _wait(0.1)
	var loaded: Variant = _last("avatar_loaded")
	_check(loaded != null and loaded.id == load_cmd.id, "avatar_loaded(%s)" % load_cmd.id)
	var compressed := 0
	for mi: Node in _character.body().find_children("*", "MeshInstance3D", true, false):
		var mesh := (mi as MeshInstance3D).mesh
		for s in (mesh.get_surface_count() if mesh else 0):
			if mesh is ArrayMesh and (mesh as ArrayMesh).surface_get_format(s) & Mesh.ARRAY_FLAG_COMPRESS_ATTRIBUTES:
				compressed += 1
	_check(compressed == 0, "no compressed mesh surfaces (%d)" % compressed)
	if label.begins_with("tsukuyomi"):
		var surfaces := 0
		for mi: Node in _character.body().find_children("*", "MeshInstance3D", true, false):
			surfaces += (mi as MeshInstance3D).mesh.get_surface_count()
		_check(surfaces <= 20, "same-material surfaces merged (%d surfaces, was 94)" % surfaces)
	_bridge.inject({"type": "set_pos", "x": 900, "y": 650})
	_bridge.inject({"type": "look_at", "target": "user"})
	await _wait(0.4)
	_check_hit_rect()
	await _test_face()
	await _test_look()
	await _test_write()
	await _test_point()
	await _test_nod()
	await _test_tap()
	await _test_throw()
	await _test_supersede()
	await _test_walk()
	await _test_grab()
	await _test_naturalness()
	await _wait(0.5)
	_check_hit_rect()


# --- Tests ---------------------------------------------------------------------

func _test_face() -> void:
	var body := _character.body()
	var vrm := body as VrmBody
	_bridge.inject({"type": "emotion", "name": "happy", "weight": 1.0})
	await _wait(0.7)
	if vrm:
		_check(vrm.expression_value("happy") > 0.7, "happy -> blend shape up (%.2f)" % vrm.expression_value("happy"))
	else:
		_check(body.get("_smile").value > 0.7, "happy -> placeholder smile")
	_bridge.inject({"type": "emotion", "name": "angry", "weight": 0.8})
	await _wait(0.7)
	if vrm:
		_check(vrm.expression_value("angry") > 0.55, "angry 0.8 -> blend shape (%.2f)" % vrm.expression_value("angry"))
		_check(vrm.expression_value("happy") < 0.1, "happy fades when angry")
	_bridge.inject({"type": "emotion", "name": "surprised", "weight": 1.0})
	await _wait(0.7)
	if vrm:
		var v := vrm.expression_value("surprised") if vrm.expression_names().has("surprised") else vrm.expression_value("oh")
		_check(v > 0.4, "surprised -> blend shape or fallback mouth (%.2f)" % v)
	_bridge.inject({"type": "emotion", "name": "sleepy", "weight": 1.0})
	await _wait(0.8)
	if vrm:
		_check(_blink_value(vrm) > 0.5, "sleepy -> eyes half closed (%.2f)" % _blink_value(vrm))
	else:
		_check((body.get("_eyes")[0] as Node3D).scale.y < 0.6, "sleepy -> placeholder eyes squint")
	_bridge.inject({"type": "emotion", "name": "neutral", "weight": 1.0})
	await _wait(1.0)
	if vrm:
		_check(vrm.expression_value("angry") < 0.05 and vrm.expression_value("happy") < 0.05, "neutral clears")
		# Auto-blink: force the next blink now.
		vrm.set("_blink_timer", 0.0)
		await _wait(0.1)
		_check(_blink_value(vrm) > 0.8, "auto-blink closes the eyes (%.2f)" % _blink_value(vrm))
		vrm.set("_blink_timer", 10.0)  # no random double blink during the check
		await _wait(0.3)
		var lid_max := AvatarBody.Gaze.LID_SOFT + AvatarBody.Gaze.LID_DOWN + 0.02
		_check(_blink_value(vrm) < lid_max, "auto-blink reopens to soft lids (%.2f)" % _blink_value(vrm))

	for v: String in AvatarState.VISEMES:
		for i in 12:
			var msg := {"type": "viseme", "aa": 0.0, "ih": 0.0, "ou": 0.0, "ee": 0.0, "oh": 0.0}
			msg[v] = 1.0
			_bridge.inject(msg)
			await _wait(1.0 / 50.0)
		if vrm:
			_check(vrm.expression_value(v) > 0.8, "viseme %s -> mouth shape (%.2f)" % [v, vrm.expression_value(v)])
		else:
			_check((body.get("_mouth") as Node3D).scale.y > 1.5 or v == "ih" or v == "ee", "viseme %s -> placeholder mouth" % v)
	await _wait(0.35)
	if vrm:
		var rest := 0.0
		for v: String in AvatarState.VISEMES:
			rest = maxf(rest, vrm.expression_value(v))
		_check(rest < 0.1, "visemes decay without updates (%.3f)" % rest)
	else:
		_check((body.get("_mouth") as Node3D).scale.y < 1.2, "placeholder mouth closes")


func _test_look() -> void:
	var head := _head_css()
	_bridge.inject({"type": "look_at", "x": head.x - 400.0, "y": head.y})
	await _wait(0.8)
	var f := _head_forward()
	_check(f.x < -0.25, "look_at left turns the head left (fwd %s)" % f)
	_bridge.inject({"type": "look_at", "x": head.x + 400.0, "y": head.y - 200.0})
	await _wait(0.8)
	f = _head_forward()
	_check(f.x > 0.25 and f.y > 0.05, "look_at up-right turns the head (fwd %s)" % f)
	_bridge.inject({"type": "look_at", "target": "user"})
	await _wait(0.8)
	await _await_contact()
	f = _head_forward()
	_check(absf(f.x) < 0.3 and f.z > 0.9, "look_at user turns the face toward the camera, a little off-axis (fwd %s)" % f)
	_check(_gaze_error_deg() < 3.5, "look_at user: the eyes meet the camera (off by %.1f deg)" % _gaze_error_deg())


func _test_write() -> void:
	_bridge.sent.clear()
	var start := _clock
	_bridge.inject({"type": "gesture", "name": "write", "duration_ms": 6000})
	await _wait(0.3)
	_check(_character.state.holding_chalk, "write holds a chalk")
	var reach := _reach_css()
	var s := _shoulder_css(AvatarState.Hand.RIGHT)
	# Board on the right hand's side (screen left of the character).
	_bridge.inject({"type": "ik_target", "x": s.x - reach * 0.6, "y": s.y - reach * 0.2})
	await _wait(0.6)
	s = _shoulder_css(AvatarState.Hand.RIGHT)
	var worst := 0.0
	for off: Vector2 in [Vector2(-0.6, -0.3), Vector2(-0.45, 0.2), Vector2(-0.7, 0.0), Vector2(-0.3, -0.5)]:
		var target := s + off * reach
		_bridge.inject({"type": "ik_target", "x": target.x, "y": target.y})
		await _wait(0.35)
		worst = maxf(worst, _hand_css().distance_to(target))
	if _character.body() is VrmBody:
		_check(worst < IK_TOLERANCE_CSS, "IK hand reaches board targets (worst %.2f px, reach %.0f px)" % [worst, reach])
	else:
		_check(worst < reach, "placeholder hand follows board targets (worst %.1f px)" % worst)
	# Streamed pen head (~90 px/s): the hand trails it closely.
	var pen := s + Vector2(-0.7, -0.1) * reach
	_bridge.inject({"type": "ik_target", "x": pen.x, "y": pen.y})
	await _wait(0.4)
	var lag := 0.0
	for i in 30:
		pen.x += reach * 0.02
		_bridge.inject({"type": "ik_target", "x": pen.x, "y": pen.y})
		await _wait(1.0 / 60.0)
		lag = maxf(lag, _hand_css().distance_to(pen))
	if _character.body() is VrmBody:
		_check(lag < reach * 0.25, "hand trails a moving pen (max lag %.1f px)" % lag)
	# Out of reach: arm extends straight toward it.
	var far := s + Vector2(-3.0, -1.0) * reach
	_bridge.inject({"type": "ik_target", "x": far.x, "y": far.y})
	await _wait(0.5)
	s = _shoulder_css(AvatarState.Hand.RIGHT)
	var hand := _hand_css()
	var angle := rad_to_deg((hand - s).angle_to(far - s))
	_check(absf(angle) < 12.0 and (hand - s).length() > reach * 0.8,
		"unreachable target: arm extends toward it (angle %.1f deg, %.0f of %.0f px)" % [angle, (hand - s).length(), reach])
	# Board across the body: character turns toward it, right hand still writes.
	var across := _shoulder_css(AvatarState.Hand.RIGHT) + Vector2(reach * 0.8, -reach * 0.1)
	_bridge.inject({"type": "ik_target", "x": across.x, "y": across.y})
	await _wait(0.8)
	var err := _hand_css().distance_to(across)
	if _character.body() is VrmBody:
		_check(err < IK_TOLERANCE_CSS * 2.0, "board across the body reached (%.2f px)" % err)
	var reports := _count("hand_pos")
	var elapsed := _clock - start
	_check(absf(reports / elapsed - 30.0) < 5.0, "hand_pos at ~30 Hz (%.1f Hz)" % (reports / elapsed))
	var done := await _wait_for("gesture_done", 3.0)
	_check(done.size() > 0 and done[0].name == "write", "gesture_done(write)")
	if done.size() > 0:
		_check(absf(done[1] - start - 6.0) < 0.1, "write lasted duration_ms (%.2f s)" % (done[1] - start))
	await _wait(0.1)
	var before := _count("hand_pos")
	await _wait(0.3)
	_check(_count("hand_pos") == before, "hand_pos stops after the gesture")
	_check(not _character.state.holding_chalk, "chalk put away")


func _test_point() -> void:
	var s := _shoulder_css(AvatarState.Hand.RIGHT)
	var target := s + Vector2(-350.0, -180.0)
	_bridge.inject({"type": "look_at", "x": target.x, "y": target.y})
	_bridge.inject({"type": "gesture", "name": "point", "duration_ms": 1200})
	await _wait(0.8)
	s = _shoulder_css(AvatarState.Hand.RIGHT)
	var hand := _hand_css()
	var angle := rad_to_deg((hand - s).angle_to(target - s))
	_check(absf(angle) < 12.0, "point aims the right arm at the look_at target (%.1f deg)" % angle)
	_check((hand - s).length() > _reach_css() * 0.75, "pointing arm is extended")
	var done := await _wait_for("gesture_done", 2.0)
	_check(done.size() > 0 and done[0].name == "point", "gesture_done(point)")
	# Target on the other side: the left hand points.
	var c := _char_css()
	_bridge.inject({"type": "look_at", "x": c.x + 300.0, "y": c.y - 300.0})
	_bridge.inject({"type": "gesture", "name": "point", "duration_ms": 500})
	await _wait(0.05)
	_check(_character.state.gesture_hand == AvatarState.Hand.LEFT, "point uses the near (left) hand")
	await _wait_for("gesture_done", 2.0)
	_bridge.inject({"type": "look_at", "target": "user"})


func _test_nod() -> void:
	await _wait(0.4)
	await _await_contact()
	var rest := _head_forward()
	var start := _clock
	_bridge.inject({"type": "gesture", "name": "nod", "duration_ms": 1000})
	var peak := 0.0
	while _clock - start < 0.95:
		await _wait(1.0 / 30.0)
		peak = maxf(peak, rad_to_deg(rest.angle_to(_head_forward())))
	_check(peak > 8.0, "nod bows the head (peak %.1f deg)" % peak)
	var done := await _wait_for("gesture_done", 1.0)
	_check(done.size() > 0 and done[0].name == "nod", "gesture_done(nod)")
	if done.size() > 0:
		_check(absf(done[1] - start - 1.0) < 0.1, "nod lasted duration_ms")


func _test_tap() -> void:
	var start := _clock
	_bridge.inject({"type": "gesture", "name": "tap_desk", "duration_ms": 1300})
	var lo := INF
	var hi := -INF
	await _wait(0.3)
	while _clock - start < 1.1:
		await _wait(1.0 / 60.0)
		var y := _hand_css().y
		lo = minf(lo, y)
		hi = maxf(hi, y)
	_check(hi - lo > 8.0, "tap_desk moves the hand up and down (%.1f px)" % (hi - lo))
	var done := await _wait_for("gesture_done", 1.0)
	_check(done.size() > 0 and done[0].name == "tap_desk", "gesture_done(tap_desk)")


func _test_throw() -> void:
	var screen: Vector2 = Vector2(1280, 720) / float(_bridge.viewport_per_css())
	_bridge.sent.clear()
	var start := _clock
	_bridge.inject({"type": "gesture", "name": "throw", "duration_ms": 900})
	_bridge.inject({"type": "throw_chalk", "strength": "normal"})
	await _wait(0.2)
	_check(_character.state.holding_chalk, "throw holds the chalk until release")
	var hit := await _wait_for("chalk_impact", 3.0)
	_check(hit.size() > 0, "chalk_impact after throw")
	if hit.size() > 0:
		var p := Vector2(hit[0].x, hit[0].y)
		_check(Rect2(Vector2.ZERO, screen).has_point(p), "impact inside the window (%s)" % p)
		var expected := 0.9 * AvatarState.THROW_RELEASE + float(ChalkThrow.PROFILES.normal.time)
		_check(absf(hit[1] - start - expected) < 0.12, "chalk leaves at the release point (%.2f s, expected %.2f)" % [hit[1] - start, expected])
	await _wait(0.1)
	var thrown: Variant = _last("gesture_done")
	_check(thrown != null and thrown.name == "throw", "gesture_done(throw)")
	# Without a gesture the chalk flies at once; strength changes the flight.
	for strength: String in ["soft", "hard"]:
		_bridge.sent.clear()
		start = _clock
		_bridge.inject({"type": "throw_chalk", "strength": strength})
		hit = await _wait_for("chalk_impact", 2.0)
		var flight := float(ChalkThrow.PROFILES[strength].time)
		_check(hit.size() > 0 and absf(hit[1] - start - flight) < 0.08, "%s chalk impact after %.2f s" % [strength, flight])
		if hit.size() > 0:
			_check(Rect2(Vector2.ZERO, screen).has_point(Vector2(hit[0].x, hit[0].y)), "%s impact inside the window" % strength)
	await _wait(1.8)
	_check(int(_main.get("_chalks_alive")) == 0, "chalk nodes clean up after the dust settles")


func _test_supersede() -> void:
	_bridge.sent.clear()
	_bridge.inject({"type": "gesture", "name": "write", "duration_ms": 5000})
	await _wait(0.2)
	_bridge.inject({"type": "gesture", "name": "idle", "duration_ms": 0})
	var first: Variant = _first("gesture_done")
	_check(first != null and first.name == "write", "superseded gesture reports gesture_done at once")
	await _wait(0.05)
	_check(_count("gesture_done") == 2 and _last("gesture_done").name == "idle", "idle(0) completes next frame")


func _test_walk() -> void:
	_bridge.sent.clear()
	var c := _char_css()
	_bridge.inject({"type": "move_to", "x": c.x - 120.0, "y": c.y, "speed": 400})
	_bridge.inject({"type": "gesture", "name": "point", "duration_ms": 200})
	var arrived := await _wait_for("arrived", 2.0)
	_check(arrived.size() > 0, "move_to arrives while gesturing")
	await _wait_for("gesture_done", 1.0)


# --- Grab (picked up by the collar) -----------------------------------------------

## Drag by the collar: the body hangs from the pointer and swings (lags, sways
## back, settles, stays bounded), hit_rect follows it, the feet never go below
## the window, release drops her onto her feet and reports arrived; a move_to
## while held waits for the landing; set_pos cancels a grab.
func _test_grab() -> void:
	var body := _character.body()
	var screen: Vector2 = Vector2(1280, 720) / float(_bridge.viewport_per_css())
	_bridge.inject({"type": "set_pos", "x": 640, "y": 650})
	_bridge.inject({"type": "look_at", "target": "user"})
	await _wait(0.8)
	var nape := _css(_character.global_position + Vector3(0.0, body.grab_height(), 0.0))
	var hand := nape + Vector2(0.0, -40.0)
	_bridge.inject({"type": "grab", "x": hand.x, "y": hand.y})
	await _wait(0.6)
	_check(_character.state.grabbed and _character.state.hang > 0.99, "grab picks her up (hang %.2f)" % _character.state.hang)
	var held := _css(_character.grab_point()).distance_to(hand)
	_check(held < 3.0, "the grab point follows the pointer (%.1f px)" % held)
	if body is VrmBody:
		var skeleton: Skeleton3D = body.get("_skeleton")
		var neck: int = body.get("_bones").get("Neck", body.get("_bones")["Head"])
		var at := _css(skeleton.global_transform * skeleton.get_bone_global_pose(neck).origin).distance_to(hand)
		_check(at < 12.0, "she hangs by the nape at the pointer (%.1f px)" % at)
	var r0 := _hit_rect_now()
	var feet0 := _css(_character.global_position)
	_check(feet0.y < 650.0 - 20.0, "lifted off the ground (feet at %.0f, stood at 650)" % feet0.y)

	# Drag right: the body lags behind (feet to the left, negative swing).
	var lag := 0.0
	for i in 30:
		hand.x += 10.0
		_bridge.inject({"type": "grab", "x": hand.x, "y": hand.y})
		await process_frame
		lag = minf(lag, _character.state.swing)
	_check(rad_to_deg(lag) < -5.0 and lag > -Character.SWING_MAX + 0.01, "the body lags a drag, cushioned before the stop (swing %.1f deg)" % rad_to_deg(lag))
	# Hold still: it overshoots, sways back and settles.
	var reversals := 0
	var last := signf(_character.state.swing)
	var peak := 0.0
	var ankles := Vector2(INF, -INF)
	for i in 240:
		await process_frame
		var sw := _character.state.swing
		peak = maxf(peak, absf(sw))
		if signf(sw) != last and absf(sw) > 0.01:
			reversals += 1
			last = signf(sw)
		var kick := _kick_value()
		ankles = Vector2(minf(ankles.x, kick), maxf(ankles.y, kick))
	_check(reversals >= 2, "sways back and forth after the drag (%d reversals)" % reversals)
	_check(absf(_character.state.swing) < deg_to_rad(6.0), "the swing settles (%.1f deg after 4 s)" % rad_to_deg(_character.state.swing))
	_check(ankles.y - ankles.x > 10.0, "legs kick while dangling (knee bend range %.0f deg)" % (ankles.y - ankles.x))
	var r1 := _hit_rect_now()
	var moved := r1.get_center().x - r0.get_center().x
	_check(absf(moved - 300.0) < 40.0, "hit_rect follows the held body (moved %.0f px for a 300 px drag)" % moved)
	_check(r1.position.y < hand.y and hand.y < r1.position.y + r1.size.y * 0.45,
		"the grab point is near the top of the hit_rect (%.0f in %s)" % [hand.y, r1])
	_check(r1.size.y > 150.0 and r1.size.y < 450.0 and r1.size.x < r1.size.y * 1.6, "held hit_rect sane (%s)" % r1)

	# Violent shaking stays bounded.
	var worst := 0.0
	var finite := true
	for i in 120:
		hand.x += 90.0 if int(i / 4) % 2 == 0 else -90.0
		hand.y += 40.0 if int(i / 6) % 2 == 0 else -40.0
		_bridge.inject({"type": "grab", "x": hand.x, "y": hand.y})
		await process_frame
		worst = maxf(worst, absf(_character.state.swing))
		finite = finite and _character.global_position.is_finite() and is_finite(_character.state.swing)
	_check(finite and worst <= Character.SWING_MAX + 1e-3, "shaking stays bounded (max swing %.1f deg)" % rad_to_deg(worst))

	# The window's bottom edge is a floor while held.
	_bridge.inject({"type": "grab", "x": 640.0, "y": screen.y - 1.0})
	await _wait(1.0)
	var feet := _css(_character.global_position)
	var floor_css: float = screen.y - float(_main.get_script().get_script_constant_map()["FLOOR_MARGIN_CSS"])
	_check(feet.y <= floor_css + 1.0, "held at the bottom edge, the feet stay above it (%.1f <= %.1f)" % [feet.y, floor_css])

	# Release: a short drop onto the feet, then arrived with the feet position.
	hand = Vector2(640.0, 380.0)
	_bridge.inject({"type": "grab", "x": hand.x, "y": hand.y})
	await _wait(2.5)
	var hanging_feet := _css(_character.global_position).y
	_bridge.sent.clear()
	var start := _clock
	_bridge.inject({"type": "release"})
	var landed := await _wait_for("arrived", 2.0)
	_check(landed.size() > 0, "release: lands and reports arrived")
	if landed.size() > 0:
		var drop := float(landed[0].y) - hanging_feet
		var want := Character.DROP * _px_per_unit()
		_check(absf(drop - want) < 8.0, "drops about %.0f px onto the feet (%.1f px)" % [want, drop])
		var now := _css(_character.global_position)
		_check(now.distance_to(Vector2(landed[0].x, landed[0].y)) < 1.0, "arrived reports the feet position")
		_check(landed[1] - start < 1.2, "falls, lands and recovers in %.2f s" % (landed[1] - start))
	_check(not _character.is_held() and _character.state.hang == 0.0, "standing again after the landing")
	if body is VrmBody:
		var vrm := body as VrmBody
		await _wait(1.5)
		var ground := _character.global_position.y
		var ankle: float = vrm.get("_legs")[0].ankle
		var lf := vrm.foot_position(true)
		var rf := vrm.foot_position(false)
		_check(absf(lf.y - ground - ankle) < 0.01 and absf(rf.y - ground - ankle) < 0.01
			and not vrm.foot_swinging(true) and not vrm.foot_swinging(false), "both feet planted after landing")
	_check_hit_rect()

	# A move_to while held waits for the landing: one arrived, for the move.
	nape = _css(_character.global_position + Vector3(0.0, body.grab_height(), 0.0))
	_bridge.inject({"type": "grab", "x": nape.x, "y": nape.y - 20.0})
	await _wait(0.5)
	var before := _character.global_position
	var target := _css(before) + Vector2(150.0, 20.0)
	_bridge.inject({"type": "move_to", "x": target.x, "y": target.y, "speed": 200})
	await _wait(0.4)
	_check(_character.global_position.distance_to(before) < 0.05, "move_to waits while she is held")
	_bridge.sent.clear()
	_bridge.inject({"type": "release"})
	var moved_to := await _wait_for("arrived", 4.0)
	await _wait(0.3)
	_check(moved_to.size() > 0 and Vector2(moved_to[0].x, moved_to[0].y).distance_to(target) < 0.5 and _count("arrived") == 1,
		"after landing she walks there: one arrived, for the move (%s)" % [moved_to])

	# set_pos cancels a grab at once.
	_bridge.inject({"type": "grab", "x": 500.0, "y": 300.0})
	await _wait(0.3)
	_bridge.inject({"type": "set_pos", "x": 640, "y": 650})
	_check(not _character.is_held() and _character.state.hang == 0.0 and _css(_character.global_position).distance_to(Vector2(640, 650)) < 0.5,
		"set_pos cancels a grab")
	await _wait(0.8)


## Bend of the left leg while dangling (deg): the knee angle (VRM), or the leg's
## swing angle (the placeholder's legs are single segments).
func _kick_value() -> float:
	var body := _character.body()
	if body is VrmBody:
		var skeleton: Skeleton3D = body.get("_skeleton")
		var leg: Variant = body.get("_legs")[0]
		var hip := skeleton.get_bone_global_pose(leg.upper).origin
		var knee := skeleton.get_bone_global_pose(leg.lower).origin
		var ankle := skeleton.get_bone_global_pose(leg.end).origin
		return rad_to_deg((knee - hip).angle_to(ankle - knee))
	return rad_to_deg((body.get("_legs")[0] as Node3D).rotation.x)


func _hit_rect_now() -> Rect2:
	var r: Variant = _last_any("hit_rect")
	return Rect2(r.x, r.y, r.w, r.h)


# --- Gait limits ------------------------------------------------------------------

## A light, graceful walk that keeps the thighs under the skirt: moderate steps
## at an unhurried cadence, the knee folding in the swing, a gentle bob, no side
## waddle, a small arm swing, pelvis-relative hip flexion under
## VrmBody.HIP_FLEX_MAX and thigh-rigged skirt panels that do not split open.
func _test_gait_limits() -> void:
	var vrm := _character.body() as VrmBody
	if vrm == null:
		# Placeholder: the legs swing only a little.
		_bridge.inject({"type": "set_pos", "x": 300, "y": 650})
		await _wait(0.5)
		_bridge.inject({"type": "move_to", "x": 700, "y": 650, "speed": 180})
		var swing := 0.0
		for i in 90:
			await process_frame
			swing = maxf(swing, absf((_character.body().get("_legs")[0] as Node3D).rotation.x))
		_check(rad_to_deg(swing) < 24.0, "placeholder legs swing gently (%.1f deg)" % rad_to_deg(swing))
		await _wait_for("arrived", 3.0)
		await _wait(0.5)
		await _wait(1.0)
		var rig := (_character.get_node("Hang/Rig") as Node3D).global_basis
		for i in 2:
			var leg := _character.body().get("_legs")[i] as Node3D
			var toe := rig.inverse() * (leg.global_basis * Vector3.BACK)
			var out := rad_to_deg(atan2(toe.x, toe.z)) * (1.0 if i == 0 else -1.0)
			_check(absf(leg.position.x) >= 0.075 and out > 3.0 and out < 12.0,
				"placeholder stands hip-width, toes out (x %.3f, %.1f deg)" % [leg.position.x, out])
		return
	var skeleton: Skeleton3D = vrm.get("_skeleton")
	var legs: Array = vrm.get("_legs")
	var hips: int = vrm.get("_bones")["Hips"]
	var leg_len: float = (legs[0].len_upper + legs[0].len_lower) * skeleton.global_transform.basis.get_scale().x
	var split_bones := [skeleton.find_bone("J_Sec_L_SkirtFront1"), skeleton.find_bone("J_Sec_R_SkirtFront1"),
		skeleton.find_bone("J_Sec_L_SkirtFront2"), skeleton.find_bone("J_Sec_R_SkirtFront2")]
	await _check_stance("standing")
	# Speeds for Tsukuyomi's legs; other avatars walk proportionally (a smaller
	# body takes quicker steps at the same on-screen speed).
	var size := clampf(leg_len / 0.65, 0.5, 1.5)
	for nominal: float in [85.0, 150.0, 180.0, 260.0]:
		var speed := nominal * size
		_bridge.inject({"type": "set_pos", "x": 250, "y": 650})
		await _wait(1.0)
		_bridge.sent.clear()
		var duration := 480.0 / speed
		_bridge.inject({"type": "move_to", "x": 730, "y": 650, "speed": speed})
		var start := _clock
		var flex := 0.0
		var lift := 0.0
		var stride := 0.0
		var liftoff := [Vector3.ZERO, Vector3.ZERO]
		var was := [false, false]
		var steps := 0
		var knee := 0.0
		var sway := Vector2(INF, -INF)
		var bob := Vector2(INF, -INF)
		var arm := Vector2(INF, -INF)
		var split := [0.0]
		var on_update := func() -> void:
			if split_bones[0] >= 0 and split_bones[3] >= 0:
				split[0] = maxf(split[0], _skirt_split(vrm, skeleton, split_bones))
		skeleton.skeleton_updated.connect(on_update)
		while _first("arrived") == null and _clock - start < duration + 1.0:
			await process_frame
			var t := (_clock - start) / duration
			for i in 2:
				var leg: Variant = legs[i]
				var swinging: bool = leg.swing >= 0.0
				if swinging and not was[i]:
					liftoff[i] = leg.pos
					steps += 1
				if not swinging and was[i]:
					stride = maxf(stride, Vector2(leg.pos.x - liftoff[i].x, leg.pos.z - liftoff[i].z).length())
				if swinging and t > 0.25 and t < 0.75:
					var hipj := skeleton.get_bone_global_pose(leg.upper).origin
					var kn := skeleton.get_bone_global_pose(leg.lower).origin
					var an := skeleton.get_bone_global_pose(leg.end).origin
					knee = maxf(knee, (kn - hipj).angle_to(an - kn))
				was[i] = swinging
				flex = maxf(flex, _hip_flexion(vrm, skeleton, leg))
				if swinging and leg.swing > 0.3 and leg.swing < 0.7:
					var ankle := skeleton.global_transform * skeleton.get_bone_global_pose(leg.end).origin
					lift = maxf(lift, ankle.y - _character.global_position.y - leg.ankle)
			if t > 0.25 and t < 0.75:
				var y := (skeleton.global_transform * skeleton.get_bone_global_pose(hips).origin).y
				bob = Vector2(minf(bob.x, y), maxf(bob.y, y))
				var x := vrm.pelvis_offset().x
				sway = Vector2(minf(sway.x, x), maxf(sway.y, x))
				var left: Variant = vrm.get("_arms")[AvatarState.Hand.LEFT]
				var d := skeleton.get_bone_global_pose(left.lower).origin - skeleton.get_bone_global_pose(left.upper).origin
				var a := atan2(d.dot(vrm.get("_forward")), -d.y)
				arm = Vector2(minf(arm.x, a), maxf(arm.y, a))
		skeleton.skeleton_updated.disconnect(on_update)
		var ppu := _px_per_unit()
		var flex_cap := VrmBody.HIP_FLEX_MAX + (deg_to_rad(3.0) if nominal > 200.0 else 0.0)
		var cadence := steps / (_clock - start)
		print("  gait %d px/s: %.2f steps/s, stride %.0f px (%.2f legs), foot lift %.1f px, knee in swing %.0f deg, pelvis bob %.1f px, side sway %.1f px, hip flexion %.1f deg, arm swing %.1f deg, skirt split %.1f deg" % [
			speed, cadence, stride * ppu, stride / leg_len, lift * ppu, rad_to_deg(knee), (bob.y - bob.x) * ppu,
			(sway.y - sway.x) * ppu, rad_to_deg(flex), rad_to_deg(arm.y - arm.x), split[0]])
		var stride_cap := 1.3 if nominal > 200.0 else 1.2 if nominal > 120.0 else 1.05
		_check(stride / leg_len < stride_cap, "%d px/s: moderate steps (stride %.2f leg lengths)" % [speed, stride / leg_len])
		if nominal < 100.0:
			_check(cadence > 1.9 and cadence < 2.9, "%d px/s: unhurried cadence (%.2f steps/s)" % [speed, cadence])
		_check(lift * ppu > 1.5 and lift * ppu < 8.0, "%d px/s: light foot lift mid-step (%.1f px)" % [speed, lift * ppu])
		_check(rad_to_deg(knee) > 20.0 and rad_to_deg(knee) < (42.0 if nominal < 100.0 else 47.0), "%d px/s: the knee folds in the swing (%.0f deg)" % [speed, rad_to_deg(knee)])
		_check((bob.y - bob.x) * ppu < (5.0 if nominal > 200.0 else 3.0), "%d px/s: gentle pelvis bob (%.1f px)" % [speed, (bob.y - bob.x) * ppu])
		_check((sway.y - sway.x) * ppu < 1.6, "%d px/s: no side-to-side waddle (%.1f px)" % [speed, (sway.y - sway.x) * ppu])
		_check(flex < flex_cap, "%d px/s: hip flexion stays under %.0f deg (%.1f)" % [speed, rad_to_deg(flex_cap), rad_to_deg(flex)])
		_check(rad_to_deg(arm.y - arm.x) > 8.0 and rad_to_deg(arm.y - arm.x) < 22.0, "%d px/s: small, visible arm swing (%.1f deg)" % [speed, rad_to_deg(arm.y - arm.x)])
		if split_bones[0] >= 0 and split_bones[3] >= 0:
			_check(split[0] < (30.0 if nominal > 200.0 else 25.0), "%d px/s: skirt front panels stay together (split %.1f deg)" % [speed, split[0]])
	_bridge.inject({"type": "set_pos", "x": 640, "y": 650})
	_bridge.inject({"type": "move_to", "x": 400, "y": 650})
	await _wait_for("arrived", 6.0)
	await _wait(2.0)
	await _check_stance("standing after walks")
	if _label.begins_with("tsukuyomi"):
		_check(vrm.cloth_count() == 4, "thigh-rigged skirt panels hang from the pelvis (%d)" % vrm.cloth_count())
		# The generic leg-collider path (for skirts without thigh colliders) runs cleanly.
		var secondary: Node = null
		for node: Node in vrm.find_children("secondary", "", true, false):
			secondary = node
		var added: int = vrm.call("_ensure_leg_colliders", secondary, true) if secondary != null else 0
		await _wait(0.3)
		var chains: Array = secondary.get("spring_bones") if secondary != null else []
		var runtime: Array = secondary.get("colliders_internal") if secondary != null else []
		_check(added == 6 and runtime.size() > 8, "runtime leg colliders attach to skirt chains (%d chains, %d colliders)" % [added, runtime.size()])
		_bridge.inject({"type": "load_avatar", "id": "default"})  # fresh springs for the next tests
		await _wait(0.2)
	await _wait(0.5)


## Standing: feet about hip-width apart and toed slightly out, the thighs not
## turned inward, the knees not closer together than the ankles (no pigeon toes
## or knock knees), also after walking (no twist creeping into the legs).
func _check_stance(what: String) -> void:
	var vrm := _character.body() as VrmBody
	var skeleton: Skeleton3D = vrm.get("_skeleton")
	var fwd: Vector3 = vrm.get("_forward")
	var left: Vector3 = vrm.get("_left")
	var bones: Dictionary = vrm.get("_bones")
	var rest: Dictionary = vrm.get("_rest_global")
	var hips := Vector2.ZERO
	var knees := Vector2.ZERO
	var ankles := Vector2.ZERO
	var report := ""
	var ok := true
	for leg: Variant in vrm.get("_legs"):
		var side: float = leg.side
		var i := 0 if side > 0.0 else 1
		var ankle := skeleton.get_bone_global_pose(leg.end).origin
		hips[i] = skeleton.get_bone_global_pose(leg.upper).origin.dot(left)
		knees[i] = skeleton.get_bone_global_pose(leg.lower).origin.dot(left)
		ankles[i] = ankle.dot(left)
		var toes: int = bones.get("LeftToes" if side > 0.0 else "RightToes", -1)
		var foot_q := skeleton.get_bone_global_pose(leg.end).basis.get_rotation_quaternion() * (rest[leg.end] as Quaternion).inverse()
		var toe := skeleton.get_bone_global_pose(toes).origin - ankle if toes >= 0 else foot_q * fwd
		var yaw := rad_to_deg(atan2(toe.dot(left) * side, toe.dot(fwd)))
		var q := skeleton.get_bone_global_pose(leg.upper).basis.get_rotation_quaternion() * (rest[leg.upper] as Quaternion).inverse()
		var thigh := q * fwd
		var twist := rad_to_deg(atan2(thigh.dot(left) * side, thigh.dot(fwd)))
		report += " %s toes %+.1f thigh %+.1f;" % ["L" if side > 0.0 else "R", yaw, twist]
		ok = ok and yaw > 2.0 and yaw < 14.0 and twist > -2.0 and twist < 16.0
	var ppu := _px_per_unit() * skeleton.global_transform.basis.get_scale().x
	var hip_w := absf(hips.x - hips.y) * ppu
	var knee_w := absf(knees.x - knees.y) * ppu
	var ankle_w := absf(ankles.x - ankles.y) * ppu
	_check(ok, "%s: toes slightly out, thighs not turned in (%s)" % [what, report])
	# Knees on (or outside) the line from the hips to the ankles: not knocked in.
	_check(ankle_w > hip_w * 0.85 and knee_w > (hip_w + ankle_w) * 0.5 - 1.5,
		"%s: feet at least hip-width, knees not together (hips %.1f, knees %.1f, ankles %.1f px)" % [what, hip_w, knee_w, ankle_w])


## Pelvis-relative hip flexion (forward, radians) of a leg.
func _hip_flexion(vrm: VrmBody, skeleton: Skeleton3D, leg: Variant) -> float:
	var hips: int = vrm.get("_bones")["Hips"]
	var rest: Quaternion = vrm.get("_rest_global")[hips]
	var q := skeleton.get_bone_global_pose(hips).basis.get_rotation_quaternion()
	var fwd: Vector3 = vrm.get("_forward")
	var v := rest * (q.inverse() * (skeleton.get_bone_global_pose(leg.lower).origin - skeleton.get_bone_global_pose(leg.upper).origin))
	var r := skeleton.get_bone_global_rest(leg.lower).origin - skeleton.get_bone_global_rest(leg.upper).origin
	return atan2(v.dot(fwd), -v.y) - atan2(r.dot(fwd), -r.y)


## Angle (deg) between the left and right front skirt panels, pelvis frame.
func _skirt_split(vrm: VrmBody, skeleton: Skeleton3D, bones: Array) -> float:
	var hips: int = vrm.get("_bones")["Hips"]
	var rest: Quaternion = vrm.get("_rest_global")[hips]
	var q := skeleton.get_bone_global_pose(hips).basis.get_rotation_quaternion()
	var fwd: Vector3 = vrm.get("_forward")
	var dl := rest * (q.inverse() * (skeleton.get_bone_global_pose(bones[2]).origin - skeleton.get_bone_global_pose(bones[0]).origin))
	var dr := rest * (q.inverse() * (skeleton.get_bone_global_pose(bones[3]).origin - skeleton.get_bone_global_pose(bones[1]).origin))
	return rad_to_deg(absf(atan2(dl.dot(fwd), -dl.y) - atan2(dr.dot(fwd), -dr.y)))


# --- Gaze life ----------------------------------------------------------------------

## Looking at the user is soft: eye contact broken by glances away (with blinks),
## micro-saccades, soft lids, the head turning only part of the way; without a
## look target she looks around instead of staring.
func _test_gaze_life() -> void:
	var body := _character.body()
	var vrm := body as VrmBody
	var gaze: AvatarBody.Gaze = body.call("gaze")
	_bridge.inject({"type": "set_pos", "x": 640, "y": 650})
	_bridge.inject({"type": "gesture", "name": "idle", "duration_ms": 0})
	_bridge.inject({"type": "look_at", "target": "user"})
	await _wait(0.5)
	# 16 s of listening: glances away and back, mostly eye contact.
	var shifts0 := gaze.shifts
	var saccades0 := gaze.saccades
	var glances := 0
	var was_away := gaze.away
	var contact := 0
	var frames := 0
	var off_during_glance := 0.0
	var coupled := 0
	var last_shift := -10.0
	var shifts_seen := gaze.shifts
	var blink_t := 1.0
	var lid_min := INF
	var t0 := _clock
	while _clock - t0 < 16.0:
		await process_frame
		frames += 1
		if gaze.shifts != shifts_seen:
			shifts_seen = gaze.shifts
			last_shift = _clock
		if gaze.away and not was_away:
			glances += 1
		was_away = gaze.away
		if not gaze.away:
			contact += 1
		else:
			off_during_glance = maxf(off_during_glance, _gaze_error_deg())
		if vrm:
			var bt: float = vrm.get("_blink_t")
			if bt < blink_t and _clock - last_shift < 0.1:
				coupled += 1
			blink_t = bt
			if bt > 0.4:
				lid_min = minf(lid_min, _blink_value(vrm))
	var fraction := float(contact) / frames
	_check(glances >= 3, "look_at user: glances away now and then (%d in 16 s)" % glances)
	_check(fraction > 0.55 and fraction < 0.95, "look_at user: mostly eye contact (%.0f%%)" % (fraction * 100.0))
	_check(off_during_glance > 6.0, "glances really leave the user (%.1f deg)" % off_during_glance)
	_check(gaze.saccades - saccades0 >= 8, "micro-saccades keep the eyes alive (%d in 16 s)" % (gaze.saccades - saccades0))
	_check(gaze.shifts - shifts0 >= 2 * glances - 1, "gaze shifts counted (%d)" % (gaze.shifts - shifts0))
	if vrm:
		_check(coupled >= 2, "gaze shifts come with blinks (%d)" % coupled)
		_check(lid_min > 0.05 and lid_min < 0.35, "soft lids, not a wide-open stare (%.2f)" % lid_min)

	# Body turned 40 deg (writing across it): the head turns only part way, the eyes the rest.
	var s := _shoulder_css(AvatarState.Hand.RIGHT)
	_bridge.inject({"type": "gesture", "name": "write", "duration_ms": 4000})
	_bridge.inject({"type": "ik_target", "x": s.x + 70.0, "y": s.y})
	await _wait(1.2)
	_bridge.inject({"type": "look_at", "target": "user"})
	await _wait(1.5)
	var rig: Node3D = _character.get_node("Hang/Rig")
	var rig_fwd := rig.global_basis.z
	var need := rad_to_deg(atan2(-rig_fwd.x, rig_fwd.z))  # yaw from the body to the camera
	var head := _head_forward()
	var turned := rad_to_deg(atan2(head.x, head.z) - atan2(rig_fwd.x, rig_fwd.z))
	var share := turned / need if absf(need) > 1.0 else 0.0
	_check(absf(need) > 25.0 and share > 0.3 and share < (0.8 if vrm else 0.9),
		"body turned %.0f deg: the head turns only %.0f%% toward the user" % [need, share * 100.0])
	_check(_gaze_error_deg() < 4.0, "... and the eyes still meet the user (off by %.1f deg)" % _gaze_error_deg())
	await _wait_for("gesture_done", 4.0)

	# No look target (idle): she looks around instead of staring at the user.
	_character.set("_look_mode", AvatarState.Look.FORWARD)
	await _wait(0.5)
	var at_user := 0
	frames = 0
	var yaw := Vector2(INF, -INF)
	var twisted := 0.0
	t0 = _clock
	while _clock - t0 < 15.0:
		await process_frame
		frames += 1
		if _gaze_error_deg() < 4.0:
			at_user += 1
		var look: Vector2 = vrm.look_angles()[0] if vrm else Vector2((body.get("_look") as AvatarBody.Spring3).value.x, 0.0)
		yaw = Vector2(minf(yaw.x, look.x), maxf(yaw.y, look.x))
		twisted = maxf(twisted, absf(gaze.twist))
	_check(float(at_user) / frames < 0.6, "idle: does not stare at the user (%.0f%% of the time)" % (100.0 * at_user / frames))
	_check(rad_to_deg(yaw.y - yaw.x) > 10.0, "idle: looks around (head yaw range %.0f deg)" % rad_to_deg(yaw.y - yaw.x))
	_check(rad_to_deg(twisted) > 4.0, "idle: sometimes turns the upper body to a 3/4 pose (%.0f deg)" % rad_to_deg(twisted))
	_bridge.inject({"type": "look_at", "target": "user"})
	await _wait(0.5)


## Waits until the gaze has held eye contact for `hold` seconds (or times out).
func _await_contact(hold := 0.6, timeout := 10.0) -> bool:
	var gaze: AvatarBody.Gaze = _character.body().call("gaze")
	var since := -1.0
	var until := _clock + timeout
	while _clock < until:
		if gaze.away:
			since = -1.0
		elif since < 0.0:
			since = _clock
		elif _clock - since >= hold:
			return true
		await process_frame
	return false


## Angle (deg) between where the eyes look (head + eyes) and the camera.
func _gaze_error_deg() -> float:
	var body := _character.body()
	var user: Vector2 = body.call("_dir_goal", Vector3.BACK)
	var eyes: Vector2
	if body is VrmBody:
		var a := (body as VrmBody).look_angles()
		eyes = a[0] + a[1]
	else:
		var look: Vector3 = (body.get("_look") as AvatarBody.Spring3).value
		eyes = Vector2(look.x, look.y) + (body.get("_eye_look") as Vector2)
	return rad_to_deg((eyes - user).length())


# --- Naturalness ----------------------------------------------------------------

func _test_naturalness() -> void:
	_bridge.inject({"type": "set_pos", "x": 900, "y": 650})
	_bridge.inject({"type": "look_at", "target": "user"})
	_bridge.inject({"type": "gesture", "name": "idle", "duration_ms": 0})
	await _wait(1.0)
	await _test_move_profile()
	await _test_gait_limits()
	await _test_shuffle_follow()
	await _test_turn_steps()
	await _test_idle_life()
	await _test_gaze_life()
	await _test_write_reach()
	await _test_wrist_wiggle()
	await _test_point_overshoot()
	await _test_nod_rebound()
	await _test_expression_easing()


## Eased move: arrives after distance / speed, starts and ends slowly; planted
## feet never slide; the feet come together after stopping.
func _test_move_profile() -> void:
	var vrm := _character.body() as VrmBody
	var start := _clock
	var from := _char_css()
	_bridge.sent.clear()
	_bridge.inject({"type": "move_to", "x": from.x - 300.0, "y": from.y, "speed": 180})
	var speeds: Array[float] = []
	var slide := 0.0
	var steps := 0
	var was_swinging := [true, true]
	var planted := [Vector3.ZERO, Vector3.ZERO]
	while _first("arrived") == null and _clock - start < 3.0:
		await process_frame
		speeds.append(absf(_character.state.velocity.x) * _px_per_unit())
		if vrm:
			for i in 2:
				var left := i == 0
				var swinging := vrm.foot_swinging(left)
				var pos := vrm.foot_position(left)
				if swinging and not was_swinging[i]:
					steps += 1
				if not swinging and not was_swinging[i]:
					slide = maxf(slide, absf(pos.x - (planted[i] as Vector3).x))
				planted[i] = pos
				was_swinging[i] = swinging
	var took := _clock - start
	_check(absf(took - 300.0 / 180.0) < 0.06, "eased move keeps the arrival time (%.2f s, want %.2f)" % [took, 300.0 / 180.0])
	var average := 180.0
	var early := speeds[int(speeds.size() * 0.04)]
	var late := speeds[int(speeds.size() * 0.97)]
	var peak := 0.0
	for v in speeds:
		peak = maxf(peak, v)
	_check(early < average * 0.6 and late < average * 0.6 and peak > average * 1.02,
		"speed eases in and out (start %.0f, peak %.0f, end %.0f px/s)" % [early, peak, late])
	if vrm:
		_check(steps >= 4, "walk takes steps (%d)" % steps)
		_check(slide * _px_per_unit() < 0.5, "planted feet do not slide (max %.2f px)" % (slide * _px_per_unit()))
		await _wait(1.5)
		var l := vrm.foot_position(true)
		var r := vrm.foot_position(false)
		var c := _character.global_position
		_check(not vrm.foot_swinging(true) and not vrm.foot_swinging(false) and l.x > r.x - 0.02
			and absf((l.x + r.x) * 0.5 - c.x) < 0.08, "feet settle under the body after stopping")
	else:
		await _wait(1.0)


## Director-style follow while writing: short hops every ~0.2 s side-step with
## the body kept toward the board, and the stance never splays.
func _test_shuffle_follow() -> void:
	var vrm := _character.body() as VrmBody
	var s := _shoulder_css(AvatarState.Hand.RIGHT)
	_bridge.inject({"type": "gesture", "name": "write", "duration_ms": 4000})
	_bridge.inject({"type": "ik_target", "x": s.x + 50.0, "y": s.y})
	await _wait(0.8)
	var yaw0: float = _character.get_node("Hang/Rig").rotation.y
	var c := _char_css()
	var rest_width := absf(vrm.foot_position(true).x - vrm.foot_position(false).x) if vrm else 0.0
	var max_shuffle := 0.0
	var max_yaw := 0.0
	var max_width := 0.0
	var steps := 0
	var was := [false, false]
	for hop in 6:
		c.x += 30.0
		_bridge.inject({"type": "move_to", "x": c.x, "y": c.y, "speed": 100})
		_bridge.inject({"type": "ik_target", "x": s.x + 50.0 + 30.0 * (hop + 1), "y": s.y})
		for f in 12:
			await process_frame
			max_shuffle = maxf(max_shuffle, _character.state.shuffle)
			max_yaw = maxf(max_yaw, absf(_character.get_node("Hang/Rig").rotation.y - yaw0))
			if vrm:
				max_width = maxf(max_width, absf(vrm.foot_position(true).x - vrm.foot_position(false).x))
				for i in 2:
					var swinging := vrm.foot_swinging(i == 0)
					if swinging and not was[i]:
						steps += 1
					was[i] = swinging
	_check(max_shuffle > 0.9, "short moves side-step (shuffle %.2f)" % max_shuffle)
	_check(rad_to_deg(max_yaw) < 12.0, "side-stepping keeps facing the board (turned %.1f deg)" % rad_to_deg(max_yaw))
	if vrm:
		var widen := (max_width - rest_width) * _px_per_unit()
		_check(steps >= 3 and widen < 35.0, "shuffle steps stay small (%d steps, stance +%.0f px)" % [steps, widen])
	_bridge.inject({"type": "gesture", "name": "idle", "duration_ms": 0})
	await _wait(1.2)


## Turning in place steps the feet around instead of spinning on them.
func _test_turn_steps() -> void:
	var vrm := _character.body() as VrmBody
	if vrm == null:
		return
	var s := _shoulder_css(AvatarState.Hand.RIGHT)
	_bridge.inject({"type": "gesture", "name": "write", "duration_ms": 1500})
	_bridge.inject({"type": "ik_target", "x": s.x + 60.0, "y": s.y})
	var stepped := false
	for f in 70:
		await process_frame
		stepped = stepped or vrm.foot_swinging(true) or vrm.foot_swinging(false)
	_check(stepped, "turning toward the board takes a step")
	await _wait_for("gesture_done", 1.5)
	await _wait(1.0)


## Idle life: breathing moves the chest, weight shifts move the hips.
func _test_idle_life() -> void:
	var body := _character.body()
	body.set("_shift_timer", 100.0)
	body.set("_shift_goal", 0.0)
	await _wait(2.0)
	var x0 := _pelvis_x(body)
	body.set("_shift_goal", 1.0)
	await _wait(2.5)
	var moved := absf(_pelvis_x(body) - x0)
	_check(moved * _px_per_unit() > 2.0, "idle weight shift moves the hips (%.1f px)" % (moved * _px_per_unit()))
	body.set("_shift_timer", 1.0)
	if body is VrmBody:
		var skeleton: Skeleton3D = body.get("_skeleton")
		var bones: Dictionary = body.get("_bones")
		var chest: int = bones.get("UpperChest", bones.get("Chest", -1))
		var lo := INF
		var hi := -INF
		for i in 60:
			await _wait(0.05)
			var a := skeleton.get_bone_global_pose(chest).basis.get_euler().x
			lo = minf(lo, a)
			hi = maxf(hi, a)
		_check(rad_to_deg(hi - lo) > 0.3, "breathing moves the chest (%.2f deg)" % rad_to_deg(hi - lo))


func _pelvis_x(body: AvatarBody) -> float:
	if body is VrmBody:
		return (body as VrmBody).pelvis_offset().x
	return (body.get("_hips") as Node3D).position.x


## Writing reach grows with the lean: targets well past the arm's ~77 px.
func _test_write_reach() -> void:
	if not _character.body() is VrmBody:
		return
	await _wait(0.5)
	var s := _shoulder_css(AvatarState.Hand.RIGHT)
	_bridge.inject({"type": "gesture", "name": "write", "duration_ms": 12000})
	var report := ""
	for probe: Array in [["right", Vector2(110.0, 0.0)], ["left", Vector2(-100.0, 10.0)], ["down", Vector2(30.0, 90.0)], ["up", Vector2(20.0, -70.0)]]:
		var target: Vector2 = s + probe[1]
		_bridge.inject({"type": "ik_target", "x": target.x, "y": target.y})
		await _wait(1.4)
		var err := _hand_css().distance_to(target)
		report += " %s %.1f px" % [probe[0], err]
		_check(err < 4.0, "writing reaches %s (%.0f px from the resting shoulder, error %.1f px)" % [probe[0], (probe[1] as Vector2).length(), err])
	print("  reach envelope errors:", report)
	_bridge.inject({"type": "gesture", "name": "idle", "duration_ms": 0})
	await _wait(1.5)


## The wrist follows the stroke with a small wiggle; the chalk stays on the pen.
func _test_wrist_wiggle() -> void:
	var s := _shoulder_css(AvatarState.Hand.RIGHT)
	_bridge.inject({"type": "gesture", "name": "write", "duration_ms": 3000})
	var pen := s + Vector2(40.0, -10.0)
	_bridge.inject({"type": "ik_target", "x": pen.x, "y": pen.y})
	await _wait(0.8)
	var lo := INF
	var hi := -INF
	var lag := 0.0
	for i in 60:
		pen.x += 1.2
		_bridge.inject({"type": "ik_target", "x": pen.x, "y": pen.y + 3.0 * sin(i * 0.5)})
		await process_frame
		var d := _character.body().hand_direction(AvatarState.Hand.RIGHT)
		var a := atan2(d.y, d.x)
		lo = minf(lo, a)
		hi = maxf(hi, a)
		lag = maxf(lag, _hand_css().distance_to(pen))
	if _character.body() is VrmBody:
		_check(rad_to_deg(hi - lo) > 3.0, "wrist moves with the stroke (%.1f deg)" % rad_to_deg(hi - lo))
		_check(lag < 12.0, "chalk stays on the pen while the wrist moves (%.1f px)" % lag)
	await _wait_for("gesture_done", 3.0)
	await _wait(0.8)


## Point: the arm overshoots its final extension and settles.
func _test_point_overshoot() -> void:
	var s := _shoulder_css(AvatarState.Hand.RIGHT)
	_bridge.inject({"type": "look_at", "x": s.x - 300.0, "y": s.y - 100.0})
	_bridge.inject({"type": "gesture", "name": "point", "duration_ms": 1500})
	# Distance of the hand from the shoulder: pulls in (anticipation), extends
	# past its final value (overshoot), settles.
	var low := INF
	var peak := 0.0
	var last := 0.0
	for i in 72:
		await process_frame
		last = _hand_css().distance_to(_shoulder_css(AvatarState.Hand.RIGHT))
		if last < low:
			low = last
			peak = 0.0
		peak = maxf(peak, last)
	if _character.body() is VrmBody:  # the placeholder arm is one rigid segment
		_check(peak > last + 1.0 and peak < last * 1.2, "point pulls in, overshoots and settles (in %.1f, peak %.1f, final %.1f px)" % [low, peak, last])
		var arm: Variant = _character.body().get("_arms")[AvatarState.Hand.RIGHT]
		_check(arm.applied_index < 0.15 and arm.applied_curl > 0.75, "pointing hand: index out, fingers curled")
	await _wait_for("gesture_done", 1.0)
	_bridge.inject({"type": "look_at", "target": "user"})
	await _wait(0.8)


## Nod: the head rebounds slightly past level after bowing.
func _test_nod_rebound() -> void:
	await _await_contact()
	var rest := _head_forward().y
	_bridge.inject({"type": "gesture", "name": "nod", "duration_ms": 600})
	var high := -INF
	var low := INF
	for i in 70:
		await process_frame
		var y := _head_forward().y
		high = maxf(high, y)
		low = minf(low, y)
	_check(low < rest - 0.15 and high > rest + 0.02, "nod bows and rebounds (low %.2f, high %.2f, rest %.2f)" % [low, high, rest])
	await _wait(0.5)


## Expressions ease in: slow start, full after a moment.
func _test_expression_easing() -> void:
	_bridge.inject({"type": "emotion", "name": "neutral", "weight": 1.0})
	await _wait(1.0)
	_bridge.inject({"type": "emotion", "name": "happy", "weight": 1.0})
	await _wait(0.05)
	var early := _happy_value()
	await _wait(0.9)
	var late := _happy_value()
	_check(early < 0.15 and late > 0.9, "expression eases in (%.2f after 50 ms, %.2f after 1 s)" % [early, late])
	_bridge.inject({"type": "emotion", "name": "neutral", "weight": 1.0})
	await _wait(0.5)


func _happy_value() -> float:
	var body := _character.body()
	if body is VrmBody:
		return (body as VrmBody).expression_value("happy")
	return body.get("_smile").value


func _blink_timing_test() -> void:
	_label = "blinks"
	var doubles := 0
	var long := 0
	for i in 500:
		var d := AvatarBody.next_blink_delay()
		if d < 0.5:
			doubles += 1
		elif d >= 2.5:
			long += 1
	_check(doubles > 40 and doubles < 150 and long + doubles == 500,
		"blink timing: mostly 2.5-6 s with occasional double blinks (%d/500)" % doubles)


func _frame_cap_test() -> void:
	_label = "frame cap"
	_main.set("frame_cap_enabled", true)
	_bridge.inject({"type": "emotion", "name": "neutral", "weight": 1.0})
	await _wait(0.1)
	_check(Engine.max_fps == 60, "active -> 60 fps")
	await _wait(2.4)
	_check(Engine.max_fps == 30, "idle > 2 s -> 30 fps")
	_bridge.inject({"type": "look_at", "target": "user"})
	await process_frame
	_check(Engine.max_fps == 60, "command -> back to 60 fps")
	_main.set("frame_cap_enabled", false)
	Engine.max_fps = 0


# --- Helpers ---------------------------------------------------------------------

func _check(ok: bool, what: String) -> void:
	_checks += 1
	print("  [%s] %s" % ["ok" if ok else "FAIL", what])
	if not ok:
		_failures.append("%s: %s" % [_label, what])


func _check_hit_rect() -> void:
	var r: Variant = _last("hit_rect")
	if r == null:
		r = _last_any("hit_rect")
	_check(r != null and r.h > 150.0 and r.h < 450.0 and r.w > 40.0 and r.w < r.h * 1.6,
		"hit_rect sane (%s)" % [r])


func _wait(seconds: float) -> void:
	var until := _clock + seconds
	while _clock < until - 1e-6:
		await process_frame


## Waits for the next message of a type sent after now: [msg, time] or [].
func _wait_for(type: String, timeout: float) -> Array:
	var seen: int = _bridge.sent.size()
	var until := _clock + timeout
	while _clock < until:
		for i in range(seen, _bridge.sent.size()):
			if _bridge.sent[i].type == type:
				return [_bridge.sent[i], _clock]
		seen = _bridge.sent.size()
		await process_frame
	return []


func _first(type: String) -> Variant:
	for m in _bridge.sent:
		if m.type == type:
			return m
	return null


func _last(type: String) -> Variant:
	for i in range(_bridge.sent.size() - 1, -1, -1):
		if _bridge.sent[i].type == type:
			return _bridge.sent[i]
	return null


## Current hit_rect even if unchanged since the last clear (recomputed).
func _last_any(_type: String) -> Variant:
	_main.set("_last_hit_rect", Rect2())
	_main.call("_report_hit_rect")
	return _last("hit_rect")


func _count(type: String) -> int:
	var n := 0
	for m in _bridge.sent:
		if m.type == type:
			n += 1
	return n


func _css(w: Vector3) -> Vector2:
	return _main.call("world_to_css", w)


func _hand_css() -> Vector2:
	return _css(_character.hand_position())


func _shoulder_css(hand: AvatarState.Hand) -> Vector2:
	return _css(_character.body().shoulder(hand))


func _char_css() -> Vector2:
	return _css(_character.global_position)


func _head_css() -> Vector2:
	return _css(_head_world())


func _reach_css() -> float:
	var body := _character.body()
	if body is VrmBody:
		var vrm := body as VrmBody
		var arm: Variant = vrm.get("_arms")[AvatarState.Hand.RIGHT]
		var skeleton: Skeleton3D = vrm.get("_skeleton")
		return arm.reach() * skeleton.global_transform.basis.get_scale().x * _px_per_unit()
	return PlaceholderBody.REACH * _px_per_unit()


func _px_per_unit() -> float:
	return float((_main.get_script() as Script).get_script_constant_map()["PIXELS_PER_UNIT_CSS"])


func _blink_value(vrm: VrmBody) -> float:
	return vrm.expression_value("blink") if vrm.expression_names().has("blink") else vrm.expression_value("blinkleft")


func _head_world() -> Vector3:
	var body := _character.body()
	if body is VrmBody:
		var skeleton: Skeleton3D = body.get("_skeleton")
		var idx: int = body.get("_bones")["Head"]
		return skeleton.global_transform * skeleton.get_bone_global_pose(idx).origin
	return (body.get("_head") as Node3D).global_position


## World direction the face points to.
func _head_forward() -> Vector3:
	var body := _character.body()
	if body is VrmBody:
		var skeleton: Skeleton3D = body.get("_skeleton")
		var idx: int = body.get("_bones")["Head"]
		var rest: Quaternion = body.get("_rest_global")[idx]
		var q := skeleton.get_bone_global_pose(idx).basis.get_rotation_quaternion() * rest.inverse()
		return (skeleton.global_transform.basis * (q * (body.get("_forward") as Vector3))).normalized()
	return ((body.get("_head") as Node3D).global_basis * Vector3.BACK).normalized()
