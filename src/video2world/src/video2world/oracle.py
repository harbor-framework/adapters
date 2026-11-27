"""Convert upstream Video2World reference packages into agent-format oracle submissions."""

from __future__ import annotations

import json
import shlex
import shutil
from pathlib import Path

import numpy as np

FB_ROBOT_UID = {
    "fb_pusht": "xarm7_pusher",
    "fb_droid": "panda_robotiq",
}

INHOUSE_CANDIDATE_EVALUATORS = frozenset(
    {
        "inhouse_point_robot",
        "inhouse_reviewed",
        "inhouse_wallet",
        "inhouse_fryer",
    }
)

UNAVAILABLE_REASONS = {
    "inhouse": "gt_pkg has only scene_source.usda and trajectory.npz (no 20-DoF actions.npy, scene.json geometry_npz, or camera calibration).",
    "ego_bimanual": "gt_pkg lacks wuji-bimanual-actions/1.0 left/right palm and 20-DoF finger-joint streams.",
    "ego_arm": "gt_pkg protocol sets actions=null and lacks expected/obj_poses.npy.",
    "twin": "gt_pkg uses twin_mujoco_v1 with STL clip mesh; twin_mujoco_v2 requires mjGEOM_BOX plate/walls.",
    "twin_toy": "gt_pkg uses twin_mujoco_v1 rather than twin_mujoco_v2.",
}


def _write_unavailable_solve(solution_dir: Path, reason: str) -> None:
    solve = solution_dir / "solve.sh"
    solve.write_text(
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        f"echo {shlex.quote(reason)} >&2\n"
        "exit 1\n"
    )
    solve.chmod(0o755)


def _write_copy_solve(solution_dir: Path) -> None:
    solve = solution_dir / "solve.sh"
    solve.write_text(
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        'PKG_DIR="$(cd "$(dirname "$0")" && pwd)/pkg"\n'
        "mkdir -p /workspace/pkg\n"
        'cp -a "${PKG_DIR}/." /workspace/pkg/\n'
    )
    solve.chmod(0o755)


def _convert_cloth(sample_dir: Path, pkg_dir: Path) -> None:
    """Convert base-frame cloth/1 gt_pkg into camera-frame droid-cloth-camera/1."""
    gt_pkg = sample_dir / "gt_pkg"
    cam = json.loads((sample_dir / "hidden/camera.json").read_text())
    T_base_cam = np.asarray(cam["extrinsics_base_cam"], dtype=float)
    T_cam_base = np.linalg.inv(T_base_cam)
    R_cb, t_cb = T_cam_base[:3, :3], T_cam_base[:3, 3]

    gt_scene = json.loads((gt_pkg / "scene.json").read_text())
    point = (R_cb @ np.asarray(gt_scene["table"]["point"], dtype=float) + t_cb).tolist()
    normal_vec = R_cb @ np.asarray(gt_scene["table"]["normal"], dtype=float)
    normal_vec = normal_vec / np.linalg.norm(normal_vec)

    gt_cloth = gt_scene["cloth"]
    corners = (np.asarray(gt_cloth["corners"], dtype=float) @ R_cb.T + t_cb).tolist()
    cloth = {
        "corners": corners,
        "grid": [int(x) for x in gt_cloth["grid"]],
        **{
            k: float(gt_cloth[k])
            for k in ("mass", "friction", "young", "poisson", "thickness")
        },
    }
    scene = {"table": {"point": point, "normal": normal_vec.tolist()}, "cloth": cloth}

    with np.load(gt_pkg / "actions.npz", allow_pickle=False) as z:
        gt_tcp = np.asarray(z["tcp_pose"], dtype=float)
        gt_grip = np.asarray(z["gripper_closure"], dtype=float)
        fps = float(z["fps"])

    tcp = T_cam_base[None] @ gt_tcp
    tcp[:, 3, :] = [0.0, 0.0, 0.0, 1.0]
    grip = (gt_grip > 0.5).astype(float)
    dt = 1.0 / fps

    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "scene.json").write_text(json.dumps(scene, indent=2) + "\n")
    np.savez(pkg_dir / "actions.npz", tcp_pose=tcp, gripper_closure=grip)
    (pkg_dir / "protocol.json").write_text(
        json.dumps(
            {
                "protocol_version": "3.0",
                "physics_profile": "droid-cloth-camera/1",
                "coordinate_frame": "first_camera_opencv",
                "status": "success",
                "scene": {"path": "scene.json"},
                "actions": {"path": "actions.npz", "format": "tcp_matrix_grip", "dt": dt},
            },
            indent=2,
        )
        + "\n"
    )
    shutil.copyfile(gt_pkg / "report.md", pkg_dir / "report.md")
    (pkg_dir / "source").mkdir(exist_ok=True)
    shutil.copyfile(sample_dir / "video.mp4", pkg_dir / "source/video.mp4")


def _convert_fb(sample_dir: Path, profile: str, pkg_dir: Path) -> str | None:
    """Convert supported fb gt_pkg entries into agent-compatible packages."""
    robot_uid = FB_ROBOT_UID.get(profile)
    if robot_uid is None:
        return (
            f"Video2World oracle unavailable for profile {profile}: "
            "FurnitureBench feedback controller is not shipped upstream."
        )
    gt_pkg = sample_dir / "gt_pkg"
    if not gt_pkg.is_dir():
        return f"Missing gt_pkg for {sample_dir.name}."
    shutil.copytree(gt_pkg, pkg_dir)
    protocol_path = pkg_dir / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    robot = dict(protocol.get("robot") or {})
    if robot.get("uid") == "widowx250s_bridge":
        robot["uid"] = robot_uid
        protocol["robot"] = robot
        protocol_path.write_text(json.dumps(protocol, indent=2) + "\n")
    return None


def _decimate_mesh(
    vertices: np.ndarray,
    counts: np.ndarray,
    indices: np.ndarray,
    max_faces: int = 4000,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Triangulate and voxel-cluster high-poly meshes so Isaac Sim scenes stay tractable."""
    tris: list[list[int]] = []
    offset = 0
    for c in counts:
        poly = indices[offset : offset + int(c)]
        offset += int(c)
        for j in range(1, len(poly) - 1):
            tris.append([int(poly[0]), int(poly[j]), int(poly[j + 1])])
    if not tris:
        return vertices, counts, indices
    faces = np.asarray(tris, dtype=np.int32)
    if len(faces) <= max_faces:
        return (
            vertices.astype(np.float32),
            np.full(len(faces), 3, dtype=np.int32),
            faces.reshape(-1),
        )

    extent = np.maximum(np.ptp(vertices, axis=0), 1e-6)
    vmin = vertices.min(axis=0)
    # Choose grid resolution so clustered vertex count lands near ~1,500 vertices.
    bins = max(8, round((max_faces / 2.5) ** (1.0 / 3.0) * 1.8))
    for _ in range(6):
        q = np.floor((vertices - vmin) / extent * bins).astype(np.int64)
        _, inv = np.unique(q, axis=0, return_inverse=True)
        n_clust = int(inv.max()) + 1
        sum_v = np.zeros((n_clust, 3), dtype=np.float64)
        cnt_v = np.zeros(n_clust, dtype=np.int64)
        np.add.at(sum_v, inv, vertices)
        np.add.at(cnt_v, inv, 1)
        new_v = (sum_v / cnt_v[:, None]).astype(np.float32)
        new_f = inv[faces]
        keep = (
            (new_f[:, 0] != new_f[:, 1])
            & (new_f[:, 1] != new_f[:, 2])
            & (new_f[:, 0] != new_f[:, 2])
        )
        new_f = new_f[keep]
        if len(new_f) <= max_faces or bins <= 6:
            # Drop unused vertices and reindex cleanly.
            used, remapped = np.unique(new_f.reshape(-1), return_inverse=True)
            new_v = new_v[used]
            new_f = remapped.reshape(-1, 3).astype(np.int32)
            return (
                new_v,
                np.full(len(new_f), 3, dtype=np.int32),
                new_f.reshape(-1),
            )
        bins = max(6, int(bins * 0.7))
    return (
        vertices.astype(np.float32),
        np.full(len(faces), 3, dtype=np.int32),
        faces.reshape(-1),
    )


def _extract_usd_mesh(usd_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Extract combined triangle/poly mesh geometry from a USD/USDZ asset."""
    from pxr import Usd, UsdGeom

    stage = Usd.Stage.Open(str(usd_path))
    xcache = UsdGeom.XformCache()
    all_meshes = [pr for pr in stage.Traverse() if pr.IsA(UsdGeom.Mesh)]
    non_col = [pr for pr in all_meshes if "/collision" not in str(pr.GetPath()).lower()]
    chosen = non_col if non_col else all_meshes
    verts_list, counts_list, idx_list = [], [], []
    v_off = 0
    for pr in chosen:
        mesh = UsdGeom.Mesh(pr)
        pts = np.asarray(mesh.GetPointsAttr().Get() or [], dtype=np.float32)
        fvc = np.asarray(mesh.GetFaceVertexCountsAttr().Get() or [], dtype=np.int32)
        fvi = np.asarray(mesh.GetFaceVertexIndicesAttr().Get() or [], dtype=np.int32)
        if not len(pts) or not len(fvc):
            continue
        mat = np.asarray(xcache.GetLocalToWorldTransform(pr), dtype=np.float64).T
        pts_h = np.c_[pts.astype(np.float64), np.ones(len(pts))]
        pts_w = (pts_h @ mat.T)[:, :3].astype(np.float32)
        verts_list.append(pts_w)
        counts_list.append(fvc)
        idx_list.append(fvi + v_off)
        v_off += len(pts_w)
    if not verts_list:
        raise ValueError(f"No mesh geometry found in USD asset: {usd_path}")
    return _decimate_mesh(
        np.concatenate(verts_list, axis=0),
        np.concatenate(counts_list, axis=0),
        np.concatenate(idx_list, axis=0),
    )


def _transform_scene_to_camera(scene: dict, t_cam_world: np.ndarray) -> dict:
    """Transform world-frame RoboDojo scene entities into camera_opencv frame."""
    import copy

    from scipy.spatial.transform import Rotation

    result = copy.deepcopy(scene)
    r_cw, p_cw = t_cam_world[:3, :3], t_cam_world[:3, 3]
    entities = (
        result.get("objects", [])
        + result.get("props", [])
        + ([result["table"]] if result.get("table") else [])
    )
    for ent in entities:
        ent["pos"] = (r_cw @ np.asarray(ent["pos"], dtype=float) + p_cw).tolist()
        rot = r_cw @ Rotation.from_quat(np.roll(ent["quat_wxyz"], -1)).as_matrix()
        ent["quat_wxyz"] = np.roll(Rotation.from_matrix(rot).as_quat(), 1).tolist()
    result.pop("camera", None)
    return result


def _convert_robodojo(sample_dir: Path, pkg_dir: Path) -> None:
    """Convert world-frame robodojo gt_pkg into camera-frame robodojo_camera_task_v1."""
    gt_pkg = sample_dir / "gt_pkg"
    cam = json.loads((sample_dir / "hidden/camera.json").read_text())
    t_world_cam = np.asarray(
        cam.get("camera_to_world_ros") or cam["extrinsics_base_cam"], dtype=float
    )
    t_cam_world = np.linalg.inv(t_world_cam)
    gt_scene = json.loads((gt_pkg / "scene.json").read_text())
    gt_proto = json.loads((gt_pkg / "protocol.json").read_text())

    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "assets").mkdir(exist_ok=True)
    shutil.copyfile(gt_pkg / gt_proto["actions"]["path"], pkg_dir / "actions.npy")

    entities = (
        gt_scene.get("objects", [])
        + gt_scene.get("props", [])
        + ([gt_scene["table"]] if gt_scene.get("table") else [])
    )
    for ent in entities:
        if float(ent.get("mass", 0.1)) <= 0:
            ent["mass"] = 0.1
        if ent.get("asset_path"):
            v, fvc, fvi = _extract_usd_mesh(gt_pkg / ent["asset_path"])
            scale = np.asarray(ent.get("scale", [1.0, 1.0, 1.0]), dtype=float)
            v = (v * scale[None, :]).astype(np.float32)
            npz_rel = f"assets/{ent['name']}.npz"
            np.savez(
                pkg_dir / npz_rel,
                vertices=v,
                face_vertex_counts=fvc,
                face_vertex_indices=fvi,
            )
            ent.pop("asset_path", None)
            ent["geometry_npz"] = npz_rel
            ent["size"] = np.ptp(v.astype(float), axis=0).tolist()
            ent["scale"] = [1.0, 1.0, 1.0]
        elif ent.get("geometry_npz"):
            src_npz = gt_pkg / ent["geometry_npz"]
            dst_npz = pkg_dir / ent["geometry_npz"]
            dst_npz.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src_npz, dst_npz)
            ent["scale"] = [1.0, 1.0, 1.0]

    cam_scene = _transform_scene_to_camera(gt_scene, t_cam_world)
    (pkg_dir / "scene.json").write_text(json.dumps(cam_scene, indent=2) + "\n")
    (pkg_dir / "protocol.json").write_text(
        json.dumps(
            {
                "protocol_version": "3.0",
                "physics_profile": "robodojo_camera_task_v1",
                "frame": "camera_opencv",
                "task": gt_proto["task"],
                "embodiment": gt_proto["embodiment"],
                "T_world_camera": t_world_cam.tolist(),
                "camera": {"focal_px": float(gt_scene["camera"]["focal_px"])},
                "scene_file": "scene.json",
                "actions": {
                    "path": "actions.npy",
                    "format": gt_proto["actions"]["format"],
                    "dt": gt_proto["actions"]["dt"],
                },
            },
            indent=2,
        )
        + "\n"
    )


def populate_oracle(
    evaluator: str,
    profile: str,
    sample_dir: Path,
    solution_dir: Path,
) -> bool:
    """Populate solution/pkg and solution/solve.sh for legitimately convertible tasks.

    Returns True when a convertible oracle submission was staged, False when the
    task has no legitimate agent-format oracle and solve.sh exits 1.
    """
    solution_dir.mkdir(parents=True, exist_ok=True)
    pkg_dir = solution_dir / "pkg"
    if pkg_dir.exists():
        shutil.rmtree(pkg_dir)

    if evaluator == "cloth":
        _convert_cloth(sample_dir, pkg_dir)
        _write_copy_solve(solution_dir)
        return True

    if evaluator == "robodojo_native_task":
        _convert_robodojo(sample_dir, pkg_dir)
        _write_copy_solve(solution_dir)
        return True

    if evaluator in INHOUSE_CANDIDATE_EVALUATORS:
        shutil.copytree(sample_dir / "candidate", pkg_dir)
        _write_copy_solve(solution_dir)
        return True

    if evaluator == "fb":
        err = _convert_fb(sample_dir, profile, pkg_dir)
        if err is None:
            _write_copy_solve(solution_dir)
            return True
        if pkg_dir.exists():
            shutil.rmtree(pkg_dir)
        _write_unavailable_solve(solution_dir, err)
        return False

    reason = UNAVAILABLE_REASONS.get(
        evaluator,
        f"Video2World oracle unavailable for evaluator {evaluator} ({profile}).",
    )
    _write_unavailable_solve(solution_dir, reason)
    return False
