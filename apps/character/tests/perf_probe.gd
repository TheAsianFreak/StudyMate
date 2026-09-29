extends SceneTree
## Native frame-cost probe; the same scenario as tools/perf_harness.html runs on
## the web build: idle, then a write gesture while the Director streams
## ik_target and viseme at 30 Hz. main.gd prints "[perf]" lines (FrameProfiler).
## Usage: godot --headless --path apps/character --script res://tests/perf_probe.gd -- --profile [default|placeholder|<file.vrm>]
## Headless has no renderer, so "frame" here is CPU cost only.

const PHASE_SECONDS := 4.0
const STREAM_HZ := 30.0

var _clock := 0.0


func _initialize() -> void:
	_run()


func _process(delta: float) -> bool:
	_clock += delta
	return false


func _run() -> void:
	var bridge := root.get_node("Bridge")
	var main: Node = (load("res://scenes/main.tscn") as PackedScene).instantiate()
	var viewport := SubViewport.new()
	viewport.size = Vector2i(1280, 720)
	root.add_child(viewport)
	viewport.add_child(main)
	await process_frame  # main._ready (Bridge hookup, fps cap) runs once the tree starts
	main.set("frame_cap_enabled", false)
	Engine.max_fps = 0
	var avatar := "default"
	for arg: String in OS.get_cmdline_user_args():
		if not arg.begins_with("--"):
			avatar = arg
	if avatar == "placeholder" or avatar == "default":
		bridge.inject({"type": "load_avatar", "id": avatar})
	else:
		bridge.inject({"type": "load_avatar", "id": "probe", "path": avatar})
	bridge.inject({"type": "set_pos", "x": 900, "y": 650})
	await _wait(1.0)
	print("[probe] avatar %s body %s max_fps %d cap %s" % [avatar, (main.get_node("Character") as Character).body().get_script().resource_path.get_file(), Engine.max_fps, main.get("frame_cap_enabled")])
	print("[probe] idle")
	await _wait(PHASE_SECONDS)
	print("[probe] write + 30 Hz ik_target/viseme")
	bridge.inject({"type": "gesture", "name": "write", "duration_ms": PHASE_SECONDS * 1000.0 + 500.0})
	bridge.inject({"type": "emotion", "name": "happy", "weight": 0.8})
	var until := _clock + PHASE_SECONDS
	var next := 0.0
	while _clock < until:
		if _clock >= next:
			next = _clock + 1.0 / STREAM_HZ
			var t := _clock
			bridge.inject({"type": "ik_target", "x": 830.0 + 40.0 * sin(t * 2.0), "y": 450.0 + 10.0 * sin(t * 7.0)})
			bridge.inject({"type": "viseme", "aa": absf(sin(t * 9.0)), "ih": 0.0, "ou": absf(sin(t * 5.0)) * 0.5, "ee": 0.0, "oh": 0.0})
		await process_frame
	print("[probe] done")
	quit(0)


func _wait(seconds: float) -> void:
	var until := _clock + seconds
	while _clock < until:
		await process_frame
