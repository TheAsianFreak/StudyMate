/**
 * Refuses adult avatars at import (EULA: the app may not be used for sexual purposes).
 *
 * A VRM is a glTF binary; its JSON chunk carries the VRM meta and every node, mesh,
 * material, image and blend-shape name. A model is rejected for
 * - adult words in its title, license notes or file name ("R18", "NSFW", 成人向け), or
 * - anatomy that SFW avatars do not model in part names (nipple meshes, genital shape
 *   keys), which is how NSFW avatar variants are built.
 * The VRM "sexual usage" permission flags are NOT used: they state what the author allows,
 * not what the model contains (the official, SFW Tsukuyomi-chan model sets "Allow").
 * Pixels are not inspected: there is no license-clean local NSFW image classifier to ship.
 */

export type ScreeningResult =
  { ok: true } | { ok: false; reason: 'not_vrm' | 'adult_label' | 'adult_parts'; detail: string };

/** Words that mark a whole model as adult (title, author notes, file name). */
const ADULT_LABEL =
  /(?:^|[^a-z0-9])(?:r-?18|r18g|nsfw|hentai|porn\w*|xxx|nude|naked|lewd|adult only|18\+)(?:$|[^a-z0-9])|18禁|成人向け|アダルト|エロ(?!ージョン)|ヌード|裸(?!足|眼|子)|全裸|えっち|エッチ|19금|성인용|성인 전용|야한|누드|알몸|나체/i;

/** Anatomy that SFW avatars do not model (checked on node/mesh/material/image/shape-key names). */
const ADULT_PARTS =
  /(?:^|[^a-z])(?:nipples?|areola[es]?|genitals?|genitalia|penis|vagina|vulva|pussy|clit(?:oris)?|testicles?|scrotum|pubic|pubes|anus|dick|cock)(?:$|[^a-z])|乳首|乳輪|性器|陰部|陰毛|陰茎|膣|ちんこ|ちんちん|まんこ|ペニス|クリトリス|유두|젖꼭지|성기(?!사)|음경|질구/i;

interface GltfJson {
  extensions?: Record<string, unknown>;
  extensionsUsed?: string[];
  nodes?: { name?: string }[];
  meshes?: { name?: string; extras?: { targetNames?: string[] } }[];
  materials?: { name?: string }[];
  images?: { name?: string; uri?: string }[];
}

/** The JSON chunk of a glTF binary, or null if the bytes are not a GLB. */
export function readGltfJson(bytes: Uint8Array): GltfJson | null {
  if (bytes.length < 20) return null;
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (view.getUint32(0, true) !== 0x46546c67) return null; // "glTF"
  const length = view.getUint32(12, true);
  if (view.getUint32(16, true) !== 0x4e4f534a || 20 + length > bytes.length) return null; // "JSON"
  try {
    return JSON.parse(new TextDecoder().decode(bytes.subarray(20, 20 + length))) as GltfJson;
  } catch {
    return null;
  }
}

export function screenAvatar(bytes: Uint8Array, fileName: string): ScreeningResult {
  const gltf = readGltfJson(bytes);
  if (!gltf) return { ok: false, reason: 'not_vrm', detail: fileName };

  const vrm1 = asRecord(asRecord(gltf.extensions)['VRMC_vrm']);
  const vrm0 = asRecord(asRecord(gltf.extensions)['VRM']);
  const meta1 = asRecord(vrm1['meta']);
  const meta0 = asRecord(vrm0['meta']);
  const labels = [
    fileName,
    meta1['name'],
    meta1['otherLicenseUrl'],
    meta1['thirdPartyLicenses'],
    meta0['title'],
    meta0['reference'],
    meta0['otherPermissionUrl'],
  ].filter((v): v is string => typeof v === 'string');
  for (const text of labels) {
    const hit = ADULT_LABEL.exec(text);
    if (hit) return { ok: false, reason: 'adult_label', detail: hit[0].trim() };
  }

  const blendShapes0 = asRecord(vrm0['blendShapeMaster'])['blendShapeGroups'];
  const expressions1 = asRecord(asRecord(vrm1['expressions'])['custom']);
  const parts = [
    ...(gltf.nodes ?? []).map((n) => n.name),
    ...(gltf.meshes ?? []).flatMap((m) => [m.name, ...(m.extras?.targetNames ?? [])]),
    ...(gltf.materials ?? []).map((m) => m.name),
    ...(gltf.images ?? []).map((i) => i.name ?? i.uri),
    ...(Array.isArray(blendShapes0) ? blendShapes0.map((g) => asRecord(g)['name']) : []),
    ...Object.keys(expressions1),
  ].filter((v): v is string => typeof v === 'string');
  for (const name of parts) {
    // snake_case / camelCase names: split so "Body_Nipple" and "nippleL" both match
    const words = name.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/[_.-]+/g, ' ');
    const hit = ADULT_PARTS.exec(words);
    if (hit) return { ok: false, reason: 'adult_parts', detail: name };
  }
  return { ok: true };
}

function asRecord(v: unknown): Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
    ? (v as Record<string, unknown>)
    : {};
}
