from pathlib import Path

import numpy as np
from PIL import Image

source_path = Path("static/images/avatar/avatar18.jpg")
reference_path = Path(
    "static/images/decorations/post-card-yukino-watermark-transparent.webp"
)
output_path = Path(
    "static/images/decorations/post-card-avatar18-watermark-transparent.webp"
)

credit_top = 625

with Image.open(source_path) as source_image, Image.open(reference_path) as ref_image:
    reference = ref_image.convert("RGBA")
    source = source_image.convert("RGB").resize(
        reference.size,
        Image.Resampling.LANCZOS,
    )

reference_rgba = np.asarray(reference, dtype=np.uint8)
source_rgb = np.asarray(source, dtype=np.uint8)
alpha = reference_rgba[..., 3]

# 先保留参考图的透明边缘、透明伞和底部署名。
result = reference_rgba.copy()

# 只用 avatar18 更新完全不透明的人物区域。
# y >= 625 是独立的底部署名区域，不能被原图白底覆盖。
source_mask = alpha == 255
source_mask[credit_top:, :] = False
result[source_mask, :3] = source_rgb[source_mask]

Image.fromarray(result, "RGBA").save(
    output_path,
    format="WEBP",
    lossless=True,
    method=6,
    exact=True,
)