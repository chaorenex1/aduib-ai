from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess

from backend.base_model import BaseModel
from backend.core.util.factory import auto_register


@auto_register('sensevoice')
class SenseVoice(BaseModel):
    model:AutoModel=None
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        model_path = kwargs['model_path']
        self.model = self.load_vad_model(model_path)

    def transcribe(self,audio_path:str):
        res = self.model.generate(
            input=audio_path,
            cache={},
            language="auto",  # "zn", "en", "yue", "ja", "ko", "nospeech"
            use_itn=True,
            batch_size_s=60,
            merge_vad=True,  #
            merge_length_s=15,
        )
        text = rich_transcription_postprocess(res[0]["text"])
        return text

    def load_vad_model(self, model_path):
        return AutoModel(
            model=model_path,
            trust_remote_code=True,
            remote_code="./model.py",
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30000},
            device="cuda:0",
        )