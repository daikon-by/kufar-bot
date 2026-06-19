from io import BytesIO

from PIL import Image

from kufar_bot.services.listing_collage import _grid_size, build_collage_from_images


def test_grid_size():
    assert _grid_size(1) == (1, 1)
    assert _grid_size(2) == (2, 1)
    assert _grid_size(3) == (2, 2)
    assert _grid_size(4) == (2, 2)
    assert _grid_size(6) == (3, 2)
    assert _grid_size(9) == (3, 3)


def test_build_collage_from_images():
    images = [
        Image.new("RGB", (800, 600), color=(255, 0, 0)),
        Image.new("RGB", (600, 800), color=(0, 255, 0)),
        Image.new("RGB", (500, 500), color=(0, 0, 255)),
    ]
    data = build_collage_from_images(images)
    assert data.startswith(b"\xff\xd8")
    collage = Image.open(BytesIO(data))
    assert collage.width == 1200
    assert collage.height > 0
