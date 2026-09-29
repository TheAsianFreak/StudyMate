extends Node3D
## Scene root: maps window CSS pixels to the character plane, executes Director
## commands and reports state. Holds no timeline logic; the Director owns that.

## Character scale on screen: CSS pixels per world unit (bodies are ~1.5 units tall).
const PIXELS_PER_UNIT_CSS := 160.0
## move_to without a speed (wandering): an unhurried stroll.
const DEFAULT_SPEED_CSS := 85.0
const HIT_RECT_PADDING_CSS := 4.0
## Held up, her feet never go below the window's bottom edge less this.
const FLOOR_MARGIN_CSS := 4.0
const HAND_POS_INTERVAL := 1.0 / 30.0
## Thrown chalk hits this fraction of the way from the hand to the screen centre,
## jittered and kept this far from the window edges.
const IMPACT_PULL := {"soft": 0.35, "normal": 0.5, "hard": 0.65}
const IMPACT_JITTER_CSS := Vector2(60.0, 40.0)
const IMPACT_MARGIN_CSS := 48.0
## Rendering cost control: full frame rate while anything moves, lower once idle.
const ACTIVE_FPS := 60
const IDLE_FPS := 30
const IDLE_AFTER := 2.0

## Tests switch this off to run unthrottled.
var frame_cap_enabled := true

@onready var _camera: Camera3D = $Camera3D
@onready var _character: Character = $Character
@onready var _sun: DirectionalLight3D = $Sun

var _move_target_css := Vector2.ZERO
var _last_hit_rect := Rect2()
var _hand_clock := HAND_POS_INTERVAL
var _idle_time := 0.0
var _chalks_alive := 0
var _profile_clock := 0.0
var _last_frame_usec := 0
var _is_web := OS.has_feature("web")
var _web_fps := 0


func _ready() -> void:
	# Report after Character has moved and posed this frame.
	process_priority = 10
	get_viewport().transparent_bg = true
	_sun.rotation_degrees = Vector3(-35.0, 30.0, 0.0)
	get_viewport().size_changed.connect(_update_camera)
	_update_camera()
	_character.position = css_to_world(_screen_css_size() * Vector2(0.8, 0.9))
	_character.arrived.connect(_on_arrived)
	_character.landed.connect(_on_landed)
	_character.gesture_done.connect(_on_gesture_done)
	_character.chalk_released.connect(_on_chalk_released)
	Bridge.command_received.connect(_on_command)
	_set_fps(ACTIVE_FPS)
	# Compile chalk/dust shaders now, hidden behind the body, not mid-gesture.
	var warmup := ChalkThrow.new()
	add_child(warmup)
	warmup.prewarm(_character.global_position + Vector3(0.0, AvatarBody.BODY_HEIGHT * 0.55, -1.5))
	Bridge.send({"type": "ready"})
	# The default avatar is already up; report its meta (credits) like a load.
	Bridge.send({"type": "avatar_loaded", "id": "default", "meta": _character.meta})


func _process(delta: float) -> void:
	var started := FrameProfiler.begin()
	_update_frame_cap(delta)
	_report_hand(delta)
	_report_hit_rect()
	FrameProfiler.end(&"main", started)
	if FrameProfiler.enabled:
		_profile_frame(delta)


func css_to_world(p: Vector2) -> Vector3:
	var w := _camera.project_position(Bridge.css_to_viewport(p), _camera.global_position.z)
	return Vector3(w.x, w.y, 0.0)


func world_to_css(w: Vector3) -> Vector2:
	return Bridge.viewport_to_css(_camera.unproject_position(w))


func _screen_css_size() -> Vector2:
	return Bridge.viewport_to_css(get_viewport().get_visible_rect().size)


func _update_camera() -> void:
	var vp_height := get_viewport().get_visible_rect().size.y
	_camera.size = vp_height / (PIXELS_PER_UNIT_CSS * Bridge.viewport_per_css())


# --- Commands ------------------------------------------------------------------

func _on_command(msg: Dictionary) -> void:
	_idle_time = 0.0
	if frame_cap_enabled:
		_set_fps(ACTIVE_FPS)
	var type: String = str(msg.get("type", ""))
	match type:
		"move_to":
			if not _has_xy(msg):
				_reject(type)
				return
			_move_target_css = Vector2(msg.x, msg.y)
			var speed_css := _num(msg, "speed", DEFAULT_SPEED_CSS)
			_character.move_to(css_to_world(_move_target_css), maxf(speed_css, 1.0) / PIXELS_PER_UNIT_CSS)
		"set_pos":
			if not _has_xy(msg):
				_reject(type)
				return
			_character.set_pos(css_to_world(Vector2(msg.x, msg.y)))
		"grab":
			if not _has_xy(msg):
				_reject(type)
				return
			var floor_css := _screen_css_size().y - FLOOR_MARGIN_CSS
			_character.grab(css_to_world(Vector2(msg.x, msg.y)), css_to_world(Vector2(0.0, floor_css)).y)
		"release":
			_character.release()
		"gesture":
			_character.play_gesture(str(msg.get("name", "idle")), _num(msg, "duration_ms", 0.0) / 1000.0)
		"emotion":
			_character.set_emotion(str(msg.get("name", "neutral")), _num(msg, "weight", 1.0))
		"look_at":
			if msg.get("target") == "user":
				_character.look_at_user()
			elif _has_xy(msg):
				_character.look_at_point(css_to_world(Vector2(msg.x, msg.y)))
			else:
				_reject(type)
		"ik_target":
			if not _has_xy(msg):
				_reject(type)
				return
			_character.set_ik_target(css_to_world(Vector2(msg.x, msg.y)))
		"viseme":
			_character.set_visemes(msg)
		"throw_chalk":
			_character.throw_chalk(str(msg.get("strength", "normal")))
		"load_avatar":
			_load_avatar(str(msg.get("id", "")), str(msg.get("path", "")))
		_:
			push_warning("main: unsupported command %s" % type)


func _load_avatar(id: String, path: String) -> void:
	if path.is_empty():
		var meta: Dictionary
		match id:
			"default":
				meta = _character.use_default()
			"placeholder":  # debugging aid: the procedural fallback body
				meta = _character.use_placeholder()
			_:
				Bridge.send({"type": "avatar_error", "id": id, "message": "아바타 파일 경로가 없습니다"})
				return
		Bridge.send({"type": "avatar_loaded", "id": id, "meta": meta})
		return
	var result := AvatarLoader.load_vrm(path)
	if result.has("error"):
		Bridge.send({"type": "avatar_error", "id": id, "message": result.error})
		return
	var meta := _character.use_vrm(result.scene, result.meta)
	Bridge.send({"type": "avatar_loaded", "id": id, "meta": meta})


static func _has_xy(msg: Dictionary) -> bool:
	var x: Variant = msg.get("x")
	var y: Variant = msg.get("y")
	return (x is float or x is int) and (y is float or y is int)


static func _num(msg: Dictionary, key: String, fallback: float) -> float:
	var v: Variant = msg.get(key)
	return float(v) if (v is float or v is int) else fallback


func _reject(type: String) -> void:
	push_warning("main: malformed %s command" % type)


# --- Events --------------------------------------------------------------------

func _on_arrived() -> void:
	Bridge.send({"type": "arrived", "x": _move_target_css.x, "y": _move_target_css.y})


## Landed after a release: arrived with where the feet are now.
func _on_landed() -> void:
	var feet := world_to_css(_character.global_position)
	Bridge.send({"type": "arrived", "x": feet.x, "y": feet.y})


func _on_gesture_done(gesture_name: String) -> void:
	Bridge.send({"type": "gesture_done", "name": gesture_name})


func _on_chalk_released(strength: String, origin: Vector3) -> void:
	var screen := _screen_css_size()
	var margin := minf(IMPACT_MARGIN_CSS, minf(screen.x, screen.y) * 0.25)
	var aim := world_to_css(origin).lerp(screen * 0.5, float(IMPACT_PULL.get(strength, 0.5)))
	aim += Vector2(randf_range(-1.0, 1.0), randf_range(-1.0, 1.0)) * IMPACT_JITTER_CSS
	aim = aim.clamp(Vector2(margin, margin), screen - Vector2(margin, margin))
	var aim_world := css_to_world(aim)
	var center_world := css_to_world(screen * 0.5)
	var chalk := ChalkThrow.new()
	chalk.name = "Chalk"
	add_child(chalk, true)
	_chalks_alive += 1
	chalk.tree_exited.connect(func() -> void: _chalks_alive -= 1)
	chalk.impacted.connect(_on_chalk_impact)
	chalk.launch(origin, Vector2(aim_world.x, aim_world.y), Vector2(center_world.x, center_world.y), strength)


func _on_chalk_impact(point: Vector3) -> void:
	var p := world_to_css(point)
	Bridge.send({"type": "chalk_impact", "x": p.x, "y": p.y})


# --- Reporting -----------------------------------------------------------------

## hand_pos at ~30 Hz while a hand gesture runs; silent otherwise.
func _report_hand(delta: float) -> void:
	if not _character.hand_gesture_active():
		_hand_clock = HAND_POS_INTERVAL
		return
	_hand_clock += delta
	if _hand_clock < HAND_POS_INTERVAL:
		return
	_hand_clock = minf(_hand_clock - HAND_POS_INTERVAL, HAND_POS_INTERVAL)
	var p := world_to_css(_character.hand_position())
	Bridge.send({"type": "hand_pos", "x": p.x, "y": p.y})


func _report_hit_rect() -> void:
	var box := _character.world_bounds()
	var rect := Rect2(world_to_css(box.position), Vector2.ZERO)
	for i in 8:
		rect = rect.expand(world_to_css(box.get_endpoint(i)))
	rect = rect.grow(HIT_RECT_PADDING_CSS)
	if rect.position.distance_to(_last_hit_rect.position) < 0.5 \
			and rect.size.distance_to(_last_hit_rect.size) < 0.5:
		return
	_last_hit_rect = rect
	Bridge.send({
		"type": "hit_rect",
		"x": rect.position.x, "y": rect.position.y,
		"w": rect.size.x, "h": rect.size.y,
	})


## Idle breathing and blinks read fine at 30 fps; halving the rate while nothing
## moves roughly halves idle CPU/GPU. Any command restores the full rate at once.
func _update_frame_cap(delta: float) -> void:
	if not frame_cap_enabled:
		return
	if _character.is_active() or _chalks_alive > 0:
		_idle_time = 0.0
	else:
		_idle_time += delta
	_set_fps(IDLE_FPS if _idle_time > IDLE_AFTER else ACTIVE_FPS)


## frame = wall time between frames (the whole engine iteration, rendering
## included); process = the engine's process-step time of the previous frame.
func _profile_frame(delta: float) -> void:
	var now := Time.get_ticks_usec()
	if _last_frame_usec > 0:
		FrameProfiler.add(&"frame", now - _last_frame_usec)
	_last_frame_usec = now
	FrameProfiler.add(&"process", int(Performance.get_monitor(Performance.TIME_PROCESS) * 1e6))
	FrameProfiler.add(&"physics", int(Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1e6))
	FrameProfiler.add(&"draws", int(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME) * 1000))
	FrameProfiler.next_frame()
	_profile_clock += delta
	if _profile_clock >= FrameProfiler.REPORT_INTERVAL:
		_profile_clock = 0.0
		print("[perf] fps cap %d | %s" % [Engine.max_fps, FrameProfiler.report()])


## On the web, Engine.max_fps paces frames with usleep, which spins the CPU in a
## single-threaded Emscripten build (a whole core at a 30 fps cap). There the page
## caps requestAnimationFrame instead (shell: bridge/frame-rate.ts) and we only
## report the wanted rate.
func _set_fps(fps: int) -> void:
	if _is_web:
		if Engine.max_fps != 0:
			Engine.max_fps = 0
		if fps != _web_fps:
			_web_fps = fps
			Bridge.set_frame_rate(fps)
		return
	if Engine.max_fps != fps:
		Engine.max_fps = fps
