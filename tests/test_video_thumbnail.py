import tempfile
import subprocess
import unittest
from pathlib import Path
from PIL import Image
from app.services.media import generate_video_thumbnail

class VideoThumbnailTests(unittest.TestCase):
    def test_normal_and_very_short_video(self):
        with tempfile.TemporaryDirectory() as temp:
            for duration in (1.5, 0.08):
                with self.subTest(duration=duration):
                    source = Path(temp) / f'{duration}.mp4'
                    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','testsrc2=size=320x180:rate=25','-t',str(duration),'-c:v','libx264','-threads','1','-pix_fmt','yuv420p',str(source)],check=True)
                    cover = generate_video_thumbnail(str(source),temp)
                    self.assertTrue(cover.startswith('thumbnails/video_'))
                    with Image.open(Path(temp)/cover) as image:
                        self.assertEqual(image.format,'WEBP')
                        self.assertLessEqual(max(image.size),640)
    def test_invalid_video_has_no_orphan_cover(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'invalid.mp4';source.write_bytes(b'not a video')
            self.assertEqual(generate_video_thumbnail(str(source),temp),'')
            self.assertEqual(list((Path(temp)/'thumbnails').glob('*')),[])


class VideoUploadCoverTests(unittest.IsolatedAsyncioTestCase):
    async def test_processed_upload_returns_local_cover_before_temp_cleanup(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch
        from app.services import uploads
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'source.mp4'
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','testsrc2=size=128x96:rate=12','-t','0.6','-c:v','libx264','-threads','1',str(source)],check=True)
            with patch.object(uploads,'settings',SimpleNamespace(MEDIA_DIR=temp,MAX_VIDEO_DURATION_SECONDS=30)), patch.object(uploads,'tmp_dir',return_value=Path(temp)), patch.object(uploads.pmdrive,'upload_file',new=AsyncMock(return_value='test-only-uri')) as storage:
                result=await uploads.process_video(source,'processed.mp4')
            self.assertTrue((Path(temp)/result['thumbnail_path']).is_file())
            self.assertTrue((Path(temp)/result['preview_path']).is_file())
            self.assertFalse((Path(temp)/'processed.mp4').exists())
            storage.assert_awaited_once()

if __name__=='__main__':unittest.main()
