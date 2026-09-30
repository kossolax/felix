from PySide6.QtGui import QImage

from felix.resources.png import encode_png


def test_encoded_png_round_trips_through_qt():
    rgba = bytes([255, 0, 0, 255, 0, 255, 0, 128, 0, 0, 255, 0, 10, 20, 30, 255])
    data = encode_png(2, 2, rgba)
    img = QImage.fromData(data).convertToFormat(QImage.Format.Format_RGBA8888)
    assert (img.width(), img.height()) == (2, 2)
    assert img.pixelColor(0, 0).getRgb() == (255, 0, 0, 255)
    assert img.pixelColor(1, 0).getRgb() == (0, 255, 0, 128)
    assert img.pixelColor(0, 1).alpha() == 0
    assert img.pixelColor(1, 1).getRgb() == (10, 20, 30, 255)
