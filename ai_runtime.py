"""Offline-only inference. Downloading model files belongs to prepare_ai.py."""
import os
from pathlib import Path
from threading import RLock
from matching import ClipAdapter, ScoreWeights

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / 'models' / 'clip-ViT-B-32'
DINO_FILES = ('config.json', 'preprocessor_config.json', 'model.safetensors')


class DinoPhotoAdapter:
    """Offline DINOv2 image embeddings, using the same class token as the photo trial."""
    def __init__(self, folder):
        from transformers import AutoImageProcessor, AutoModel
        self._processor = AutoImageProcessor.from_pretrained(folder, local_files_only=True, use_fast=False,
                                                              trust_remote_code=False)
        self._model = AutoModel.from_pretrained(folder, local_files_only=True, use_safetensors=True,
                                                trust_remote_code=False)
        self._model.eval()
        self._lock = RLock()

    def embed_image(self, path):
        import torch
        from PIL import Image
        with self._lock, Image.open(path) as picture, torch.inference_mode():
            inputs = self._processor(images=picture.convert('RGB'), return_tensors='pt')
            return self._model(**inputs).last_hidden_state[0, 0].tolist()


class LocalAI:
    def __init__(self):
        self.adapter = None
        self.photo_adapter = None
        self.attempted = False
        self.reason = 'Local AI has not been checked yet.'
        self.weights = ScoreWeights.from_environment()
        self._lock = RLock()

    def prepare(self):
        with self._lock:
            if self.attempted:
                return self.adapter
            self.attempted = True
            if os.getenv('ENABLE_AI', '1').casefold() not in {'1','true','yes'}:
                self.reason = 'AI is disabled in the local configuration.'
                return None
            if not (MODEL_DIR/'modules.json').is_file():
                self.reason = 'Local model is not prepared. Run SETUP_AI.bat or python3 setup_ai.py.'
                return None
            try:
                os.environ['HF_HUB_OFFLINE'] = '1'
                os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
                os.environ['TRANSFORMERS_OFFLINE'] = '1'
                from sentence_transformers import SentenceTransformer
                import torch
                torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
                model = SentenceTransformer(str(MODEL_DIR), device='cpu', local_files_only=True,
                                            trust_remote_code=False)
                model.eval()
                self.adapter = ClipAdapter(model)
                self.reason = 'CLIP is running on this server. No photos are sent externally.'
            except Exception as error:
                self.reason = 'Local model could not load ('+type(error).__name__+'). Rerun AI setup.'
            if self.adapter and os.getenv('ENABLE_DINO', '1').casefold() in {'1','true','yes'}:
                folder = MODEL_DIR.with_name('dinov2-small')
                if all((folder/file).is_file() for file in DINO_FILES):
                    try:
                        self.photo_adapter = DinoPhotoAdapter(folder)
                        self.reason = 'CLIP and DINOv2 run locally. DINOv2 compares photos when both are available.'
                    except Exception:
                        self.reason = 'CLIP is ready. DINOv2 could not load, so CLIP will compare photos.'
            return self.adapter

    def status(self):
        from dataclasses import asdict
        return dict(ready=self.adapter is not None, method='clip_ai' if self.adapter else 'typed_details',
                    reason=self.reason, model='CLIP ViT-B/32', photo_model='DINOv2 Small' if self.photo_adapter else 'CLIP ViT-B/32' if self.adapter else None,
                    weights=asdict(self.weights),
                    thresholds=dict(strong=60,possible=40), local_only=True)
