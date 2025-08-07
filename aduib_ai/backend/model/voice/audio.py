"""
使用FFmpeg从视频中提取音频
"""
import os

import ffmpeg

class Audio:

    def extract_audio(self, video_path:str)->str:
        """
        使用FFmpeg从视频中提取音频
        :param video_path: 视频路径
        :return: 音频路径
        """
        audio_dir = os.path.dirname(video_path)
        audio_name = os.path.basename(video_path).split('.')[0] + '.wav'
        audio_path = os.path.join(audio_dir, audio_name)
        # 提取视频音频并保存为 WAV 格式
        ffmpeg.input(video_path).output(audio_path, '-y',acodec='pcm_s16le', ac=2, ar='44100').run()
        return audio_path

    def slice_audio(self, audio_path:str, segment_length:int=30000)->list[str]:
        """
        使用FFmpeg切分音频
        :param audio_path: 音频路径
        :param segment_length: 最大长度
        :return: 切分后的音频路径列表
        """
        # 文件名称
        filename = os.path.basename(audio_path)
        # 输出目录
        output_dir = os.path.dirname(audio_path)
        # 音频时长
        duration = ffmpeg.probe(audio_path)['format']['duration']
        # 计算切割的片段数
        segments = int(duration // segment_length) + (1 if duration % segment_length > 0 else 0)

        # 创建输出目录，如果不存在
        os.makedirs(output_dir, exist_ok=True)

        list_output_audio_path = []
        for i in range(segments):
            start_time = i * segment_length
            output_audio_path = os.path.join(output_dir, f"{filename}_segment_{i + 1}.wav")

            # 使用 ffmpeg 从指定的起始时间截取音频片段
            ffmpeg.input(audio_path, ss=start_time, t=segment_length).output(output_audio_path,
                                                                              '-y',acodec='pcm_s16le',ac=2,ar='44100').run()
            list_output_audio_path.append(output_audio_path)

        return list_output_audio_path



