"""Lines in a picture: where a drawing's (or a photo's) lines are, how far an outline sits off them, and an outline
laid onto them as one line.

    line_map  a cost map: 0 on a line's middle, rising by 1 per px off it
    fit       an outline's miss: each point's distance to the nearest line, every 1 px along it
    follow    a rough outline moved onto the lines: each point along its own normal only, all moves chosen together
              (dynamic programming round the closed outline) so the outline stays on one line and cannot jump to an
              inner line and back

Images are a path or an array (grey, or BGR as OpenCV reads it). Needs opencv-python and numpy (the "lines" extra)."""


def _cv():
    try:
        import cv2
        import numpy as np
    except ImportError as e:
        raise ValueError("lines needs opencv-python and numpy: pip install ocrlab-mcp[lines]") from e
    return cv2, np


def _gray(image):
    cv2, np = _cv()
    if isinstance(image, str):
        g = cv2.imread(image, cv2.IMREAD_GRAYSCALE)
        if g is None:
            raise FileNotFoundError("cannot read the image: %s" % image)
        return g
    a = np.asarray(image)
    return cv2.cvtColor(a, cv2.COLOR_BGR2GRAY) if a.ndim == 3 else a


def _color(image):
    cv2, np = _cv()
    if isinstance(image, str):
        return cv2.imread(image, cv2.IMREAD_COLOR)
    a = np.asarray(image).copy()
    return cv2.cvtColor(a, cv2.COLOR_GRAY2BGR) if a.ndim == 2 else a


def line_map(image, mode="auto", threshold=None, edge_pct=94.0, low=0.35):
    """The picture's lines as a cost map (px to the nearest line's middle) and the mode used. mode "lines" (line
    art: the ridge of the ink, its middle), "photo" (the strong edges: Canny with its high threshold at the
    edge_pct percentile of the gradient), "auto" picks by how much of the picture is mid grey (a photo has much,
    clean line art almost none)."""
    cv2, np = _cv()
    g = _gray(image)
    if mode == "auto":
        mode = "photo" if float(((g > 60) & (g < 195)).mean()) > 0.08 else "lines"
    if mode == "lines":
        if threshold is None:
            _, m = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        else:
            _, m = cv2.threshold(g, threshold, 255, cv2.THRESH_BINARY_INV)
        inside = cv2.distanceTransform(m, cv2.DIST_L2, 3)               # px to the paper: peaks on the ink's middle
        peak = cv2.dilate(inside, np.ones((3, 3), np.uint8))
        centre = ((inside > 0) & (inside >= peak - 0.5)).astype(np.uint8)
    elif mode == "photo":
        # the strong edges only: Canny on the picture's own gradient, its high threshold at the edge_pct percentile of
        # the gradient's size, so a dark part on a light ground stays and a floor's grain or a halftone's dots drop out
        b = cv2.GaussianBlur(g, (0, 0), 1.6)
        dx, dy = cv2.Sobel(b, cv2.CV_16S, 1, 0), cv2.Sobel(b, cv2.CV_16S, 0, 1)
        hi = float(np.percentile(np.hypot(dx.astype(np.float32), dy.astype(np.float32)), edge_pct))
        centre = (cv2.Canny(dx, dy, low * hi, hi, L2gradient=True) > 0).astype(np.uint8)     # a weak edge kept when it joins a strong one
    else:
        raise ValueError("mode is auto, lines or photo")
    cost = cv2.distanceTransform((1 - centre).astype(np.uint8), cv2.DIST_L2, 5)
    return cost.astype(np.float32), mode


def dense(pts, step_px):
    """A closed outline cut into points step_px apart."""
    cv2, np = _cv()
    out = []
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        n = max(1, int(np.hypot(b[0] - a[0], b[1] - a[1]) / step_px))
        for k in range(n):
            out.append((a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n))
    return np.asarray(out, dtype=float)


def sample(cost, xy):
    """The cost map read at sub-pixel points (bilinear)."""
    cv2, np = _cv()
    h, w = cost.shape
    x = np.clip(xy[..., 0], 0, w - 1.001)
    y = np.clip(xy[..., 1], 0, h - 1.001)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    c = cost
    return (c[y0, x0] * (1 - fx) * (1 - fy) + c[y0, x0 + 1] * fx * (1 - fy) + c[y0 + 1, x0] * (1 - fx) * fy
            + c[y0 + 1, x0 + 1] * fx * fy)


def fit(image, outline_px, mode="auto", threshold=None, on_px=1.5, cost=None, edge_pct=94.0, low=0.35):
    """How well a closed outline (px) sits on the picture's lines: each point's distance to the nearest line's
    middle, every 1 px along it. The mean, the 95th percentile and the largest miss in px, and the share within on_px."""
    cv2, np = _cv()
    if cost is None:
        cost, mode = line_map(image, mode, threshold, edge_pct, low)
    d = sample(cost, dense([tuple(map(float, p)) for p in outline_px], 1.0))
    return {"mode": mode, "mean_px": round(float(d.mean()), 2), "p95_px": round(float(np.percentile(d, 95)), 2),
            "max_px": round(float(d.max()), 2), "on_share": round(float((d <= on_px).mean()), 3)}


def _once(cost, rough, radius_px, step_px, smooth, cap_px=12.0):
    cv2, np = _cv()
    P = dense(rough, step_px)
    n = len(P)
    t = P[(np.arange(n) + 1) % n] - P[(np.arange(n) - 1) % n]
    t /= np.linalg.norm(t, axis=1, keepdims=True) + 1e-9
    N = np.stack([-t[:, 1], t[:, 0]], 1)                         # each point's normal
    offs = np.arange(-radius_px, radius_px + 0.25, 0.5)
    K = len(offs)
    # truncated: beyond cap_px from any line every place costs the same, so where no line is in reach (a faint edge,
    # an open ground) a point stays where it was read instead of sliding toward a far line
    C = np.minimum(sample(cost, P[:, None, :] + offs[None, :, None] * N[:, None, :]), cap_px) + 0.05 * np.abs(offs)[None, :]
    pen = smooth * np.abs(offs[:, None] - offs[None, :])           # the price of a neighbour moving differently

    def run(start):
        order = [(start + i) % n for i in range(n)]
        acc = C[order[0]].copy()
        back = np.zeros((n, K), dtype=np.int32)
        for i in range(1, n):
            tot = acc[:, None] + pen
            back[i] = np.argmin(tot, axis=0)
            acc = tot[back[i], np.arange(K)] + C[order[i]]
        pick = np.zeros(n, dtype=np.int32)
        pick[n - 1] = int(np.argmin(acc))
        for i in range(n - 1, 0, -1):
            pick[i - 1] = back[i, pick[i]]
        res = np.zeros(n, dtype=np.int32)
        res[order] = pick
        return res

    first = run(0)
    sure = C[np.arange(n), first] + np.abs(np.diff(np.r_[first, first[0]]))   # on a line and steady: a safe seam
    pick = run(int(np.argmin(sure)))
    Q = P + offs[pick][:, None] * N
    c0, cm, cp = sample(cost, Q), sample(cost, Q - 0.5 * N), sample(cost, Q + 0.5 * N)
    den = cm - 2 * c0 + cp                                         # sub-pixel: a parabola through three costs
    sh = np.where(den > 1e-6, 0.25 * (cm - cp) / np.maximum(den, 1e-6), 0.0).clip(-0.5, 0.5)
    return Q + sh[:, None] * N


def _cross(a, b, c, d):
    """Where segments ab and cd cross (not at shared ends), else None."""
    r = (b[0] - a[0], b[1] - a[1])
    q = (d[0] - c[0], d[1] - c[1])
    den = r[0] * q[1] - r[1] * q[0]
    if abs(den) < 1e-12:
        return None
    t = ((c[0] - a[0]) * q[1] - (c[1] - a[1]) * q[0]) / den
    u = ((c[0] - a[0]) * r[1] - (c[1] - a[1]) * r[0]) / den
    if 1e-9 < t < 1 - 1e-9 and 1e-9 < u < 1 - 1e-9:
        return (a[0] + t * r[0], a[1] + t * r[1])
    return None


def _area(pts):
    return 0.5 * sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(pts, pts[1:] + pts[:1]))


def crossings(pts):
    """How many times a closed outline crosses itself."""
    n, c = len(pts), 0
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if _cross(pts[i], pts[(i + 1) % n], pts[j], pts[(j + 1) % n]):
                c += 1
    return c


def untangle(pts, max_loops=200):
    """A closed outline made simple: at each place it crosses itself the loop between the two crossing edges is cut
    off at the crossing point, and the larger of the two parts kept (a follower's small loop between close lines goes,
    the outline stays). A solid's cap needs a simple outline. Returns the outline and how many loops went."""
    pts = [tuple(map(float, p)) for p in pts]
    cut = 0
    while cut < max_loops:
        n, hit = len(pts), None
        for i in range(n):
            for j in range(i + 2, n):
                if i == 0 and j == n - 1:
                    continue
                x = _cross(pts[i], pts[(i + 1) % n], pts[j], pts[(j + 1) % n])
                if x:
                    hit = (i, j, x)
                    break
            if hit:
                break
        if not hit:
            break
        i, j, x = hit
        outer = pts[:i + 1] + [x] + pts[j + 1:]
        loop = [x] + pts[i + 1:j + 1]
        pts = outer if abs(_area(outer)) >= abs(_area(loop)) else loop
        cut += 1
    return [list(p) for p in pts], cut


def follow(image, rough_px, radius_px=16, step_px=2, eps_px=0.5, smooth=0.6, passes=2, fine_px=6, mode="auto",
           threshold=None, picture=None, label=None, edge_pct=94.0, low=0.35, cap_px=12.0):
    """A rough closed outline (px) laid onto the picture's lines as one line. Points step_px apart each move only
    along their own normal (up to radius_px, in 0.5 px steps); the moves are chosen together so every point lands on
    a line's middle while neighbours move alike (smooth: the price of 1 px of difference); a place more than cap_px
    from any line costs no more than cap_px, so a stretch with no line in reach stays as read. Later passes start
    from the last result and search fine_px. The result is made simple (untangle): a solid built from it needs an
    outline that does not cross itself. Gives the outline, its fit before and after, and, with picture (a path), the
    picture: the rough outline grey, the result green where within 1.5 px of a line and red where not."""
    cv2, np = _cv()
    cost, mode = line_map(image, mode, threshold, edge_pct, low)
    rough = [tuple(map(float, p)) for p in rough_px]
    if len(rough) < 3:
        raise ValueError("an outline needs at least 3 points")
    Q = None
    for _ in range(max(1, passes)):
        Q = _once(cost, rough if Q is None else [tuple(q) for q in Q], radius_px if Q is None else fine_px, step_px, smooth, cap_px)
    poly = cv2.approxPolyDP(Q.astype(np.float32).reshape(-1, 1, 2), eps_px, True)[:, 0, :]
    poly, loops = untangle([[float(x), float(y)] for x, y in poly])
    poly = [[round(x, 2), round(y, 2)] for x, y in poly]
    out = {"outline_px": poly, "points": len(poly), "mode": mode, "passes": passes, "loops_cut": loops,
           "area_px": float(abs(cv2.contourArea(Q.astype(np.float32)))),
           "fit_before": fit(image, rough, cost=cost), "fit_after": fit(image, poly, cost=cost)}
    a0 = abs(cv2.contourArea(np.asarray(rough, dtype=np.float32)))
    out["area_change"] = round(out["area_px"] / a0 - 1.0, 3) if a0 else None    # a large change: the outline collapsed or ran off
    out["fit_before"]["mode"] = out["fit_after"]["mode"] = mode
    if picture:
        img = _color(image)
        cv2.polylines(img, [np.array(rough, dtype=np.int32)], True, (160, 160, 160), 1)
        D = dense([tuple(p) for p in poly], 1.0)
        for (x, y), d in zip(D, sample(cost, D)):
            cv2.circle(img, (int(round(x)), int(round(y))), 1, (0, 170, 0) if d <= 1.5 else (0, 0, 255), -1)
        text = "%s: green on a line, red off it; p95 miss %.1f px" % (label or "FOLLOW TRACE", out["fit_after"]["p95_px"])
        cv2.rectangle(img, (0, 0), (12 + 8 * len(text), 26), (255, 255, 255), -1)
        cv2.putText(img, text, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        cv2.imwrite(str(picture), img)
        out["picture"] = str(picture)
    return out
