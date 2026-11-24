"""Subject crop keeps the item and drops a flat border."""
import unittest
from PIL import Image
from lyfind.vision_prep import brightness, even_light, isolate_subject, photo_views


class IsolateTests(unittest.TestCase):
    def test_dark_object_on_light_border_is_cropped(self):
        im = Image.new("RGB", (200, 200), (230, 230, 225))
        for x in range(70, 130):
            for y in range(80, 150):
                im.putpixel((x, y), (20, 20, 20))
        crop = isolate_subject(im)
        self.assertLess(crop.size[0] * crop.size[1], im.size[0] * im.size[1])
        views = photo_views(im)
        self.assertGreaterEqual(len(views), 5)
        self.assertEqual(views[0].size, im.size)

    def test_a_dull_photo_is_lifted_before_the_crops(self):
        dull = Image.new("RGB", (80, 80), (18, 18, 20))
        lifted = even_light(dull)
        self.assertGreater(brightness(lifted), brightness(dull) + 0.15)
        bright = Image.new("RGB", (80, 80), (210, 208, 200))
        self.assertGreater(brightness(even_light(bright)), 0.6)
