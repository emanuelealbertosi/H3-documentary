from app.runner import visual_review_images


def test_visual_review_checks_middle_and_end_of_every_scene(tmp_path):
    for name in ("01-0.15.jpg", "01-0.55.jpg", "01-0.85.jpg", "02-0.55.jpg", "02-0.85.jpg"):
        (tmp_path / name).write_bytes(b"preview")

    assert [x.name for x in visual_review_images(tmp_path)] == [
        "01-0.55.jpg", "01-0.85.jpg", "02-0.55.jpg", "02-0.85.jpg",
    ]
