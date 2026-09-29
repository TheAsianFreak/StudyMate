class_name FrameProfiler
extends RefCounted
## Opt-in frame timing, identical natively and in the web build. Enable with
## `window.studymateProfile = true` before the engine starts (web) or the user
## argument `--profile` (native, after `--`). main.gd then prints a "[perf]" line
## (browser console on the web) every REPORT_INTERVAL seconds with per-frame
## averages in milliseconds. Disabled, every call is a single bool check.

const REPORT_INTERVAL := 2.0

static var enabled := false
## Investigation switches from `window.studymateProfile = "flag,flag"` or
## `--profile=flag,flag`, honoured by VrmBody: static (no posing or face),
## nosprings (remove VRM spring bones), noface, hidehair, nomerge (keep the
## avatar's original surfaces). Used to bisect frame cost; never set in production.
static var flags: PackedStringArray = []
static var _sums: Dictionary = {}  # section -> total usec
static var _peaks: Dictionary = {}  # section -> worst single-frame usec
static var _frame: Dictionary = {}  # section -> usec in the current frame
static var _frames := 0


static func begin() -> int:
	return Time.get_ticks_usec() if enabled else 0


static func end(section: StringName, start_usec: int) -> void:
	if enabled:
		add(section, Time.get_ticks_usec() - start_usec)


static func add(section: StringName, usec: int) -> void:
	_frame[section] = int(_frame.get(section, 0)) + usec


## Closes the current frame (call once per frame).
static func next_frame() -> void:
	for section: StringName in _frame:
		var usec: int = _frame[section]
		_sums[section] = int(_sums.get(section, 0)) + usec
		_peaks[section] = maxi(int(_peaks.get(section, 0)), usec)
	_frame.clear()
	_frames += 1


## "section avg/max ms ..." over the frames since the last report; resets.
static func report() -> String:
	var parts: PackedStringArray = []
	var keys := _sums.keys()
	keys.sort()
	for section: StringName in keys:
		parts.append("%s %.2f/%.1f" % [section, _sums[section] / 1000.0 / maxi(_frames, 1), _peaks[section] / 1000.0])
	var line := "%d frames | avg/max ms: %s" % [_frames, " ".join(parts)]
	_sums.clear()
	_peaks.clear()
	_frames = 0
	return line


## Brackets the skeleton's modifier stack (spring bones etc.): add one Mark as
## the first internal child and one as the last, and the pair reports the time
## the modifiers between them took.
class Mark:
	extends SkeletonModifier3D

	static var _started := 0
	var section: StringName = &""
	var closing := false

	func _process_modification() -> void:
		if closing:
			FrameProfiler.add(section, Time.get_ticks_usec() - _started)
		else:
			_started = Time.get_ticks_usec()


## Installs a Mark pair around every modifier on the skeleton.
static func bracket_modifiers(skeleton: Skeleton3D, section: StringName) -> void:
	if not enabled or skeleton == null:
		return
	var first := Mark.new()
	first.name = "ProfileStart"
	skeleton.add_child(first, false, Node.INTERNAL_MODE_FRONT)
	skeleton.move_child(first, 0)
	var last := Mark.new()
	last.name = "ProfileEnd"
	last.section = section
	last.closing = true
	skeleton.add_child(last, false, Node.INTERNAL_MODE_BACK)
