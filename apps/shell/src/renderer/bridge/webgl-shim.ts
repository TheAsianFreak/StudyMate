/**
 * Emscripten blits Godot's offscreen back buffer to the canvas every frame and reads
 * gl.getParameter(SCISSOR_TEST) while doing so. Chrome answers that query with a
 * synchronous round trip that waits for the GPU process to drain its queue, so every
 * frame cost CPU time plus all queued GPU work (100+ ms frames under load). Tracking the
 * scissor state on the JS side keeps the query local. Same shim as character/scripts/
 * bridge.gd, installed here because the shell's CSP forbids the eval Godot would use.
 */
declare global {
  interface Window {
    studymateGlShimInstalled?: boolean;
  }
}

const SCISSOR_TEST = 0x0c11;

export function installWebGlScissorShim(): void {
  const proto = window.WebGL2RenderingContext?.prototype as
    (WebGL2RenderingContext & { __studymateScissorShim?: boolean }) | undefined;
  if (!proto || proto.__studymateScissorShim) return;
  proto.__studymateScissorShim = true;
  const state = new WeakMap<WebGL2RenderingContext, boolean>();
  const { enable, disable, getParameter, isEnabled } = proto;
  proto.enable = function (this: WebGL2RenderingContext, cap: GLenum) {
    if (cap === SCISSOR_TEST) state.set(this, true);
    return enable.call(this, cap);
  };
  proto.disable = function (this: WebGL2RenderingContext, cap: GLenum) {
    if (cap === SCISSOR_TEST) state.set(this, false);
    return disable.call(this, cap);
  };
  proto.getParameter = function (this: WebGL2RenderingContext, pname: GLenum) {
    if (pname !== SCISSOR_TEST) return getParameter.call(this, pname) as unknown;
    let on = state.get(this);
    if (on === undefined) {
      on = Boolean(getParameter.call(this, pname));
      state.set(this, on);
    }
    return on;
  } as typeof proto.getParameter;
  proto.isEnabled = function (this: WebGL2RenderingContext, cap: GLenum) {
    return cap === SCISSOR_TEST ? Boolean(this.getParameter(cap)) : isEnabled.call(this, cap);
  };
  window.studymateGlShimInstalled = true;
}
