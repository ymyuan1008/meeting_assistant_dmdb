import json
import re
from datetime import datetime
from typing import Union, Dict, Any, List
from typing import Optional, Tuple, Dict

from pydantic import BaseModel, Field, validator


# 转录文本模型
class TranscriptionBase(BaseModel):
    """转录文本基础模型"""
    speaker_id: str = Field(..., max_length=50)
    speaker_name: Optional[str] = Field(None, max_length=100)
    text: str = Field(..., min_length=1)
    confidence_score: int = Field(default=80, ge=0, le=100)

    @validator('confidence_score')
    def validate_confidence(cls, v):
        if not 0 <= v <= 100:
            raise ValueError('置信度分数必须在0到100之间')
        return v


class TranscriptionCreate(TranscriptionBase):
    meeting_id: str
    timestamp: Optional[datetime] = None



class TranscriptionResponse(TranscriptionBase):
    """转录文本响应模型"""
    id: str = Field(..., description="转录记录唯一标识")
    meeting_id: str = Field(..., description="关联的会议ID")
    timestamp: datetime = Field(
        ...,
        description="转录时间戳",
        lt=datetime.now(),
    )
    is_action_item: bool = Field(default=False, description="是否为行动项")
    is_decision: bool = Field(default=False, description="是否为决策项")

    class Config(object):
        from_attributes = True


# WebSocket消息模型
class WebSocketMessage(BaseModel):
    type: str
    meeting_id: str
    speaker_id: Optional[str] = None
    audio_data: Optional[str] = None
    text: Optional[str] = None
    timestamp: Optional[datetime] = None


# 翻译相关模型
class TranslationItem(BaseModel):
    text: str
    source_lang: str
    target_lang: str
    translated_text: str
    confidence: Optional[float] = None
    metadata: Optional[dict[str, Any]] = None


class TranslationBatch(BaseModel):
    items: list[TranslationItem]
    batch_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None

class SentenceItem(BaseModel):
    sentence: str
    progressive: str = ""

    @property
    def cleaned_sentence(self) -> str:
        """清理后的句子内容，移除说话人标记"""
        # 移除说话人标记模式：👤 说话人X:
        cleaned = re.sub(r'^\\n👤\s*说话人[A-Z]:\s*["\']?', '', self.sentence)
        cleaned = re.sub(r'["\']?$', '', cleaned)
        return cleaned.strip()

    @property
    def speaker(self) -> Optional[str]:
        """提取说话人信息"""
        match = re.search(r'👤\s*(说话人[A-Z])', self.sentence)
        return match.group(1) if match else None

    @property
    def has_content(self) -> bool:
        """判断句子是否有实际内容"""
        return bool(self.cleaned_sentence)


class TranslateTextContent(BaseModel):
    completedSentences: List[SentenceItem] = Field(default_factory=list)
    textVal: str = ""

    @property
    def valid_sentences(self) -> List[SentenceItem]:
        """获取有实际内容的句子"""
        return [item for item in self.completedSentences if item.has_content]

    @property
    def speakers(self) -> List[str]:
        """获取所有说话人列表（去重）"""
        speaker_list = [item.speaker for item in self.valid_sentences if item.speaker]
        return list(dict.fromkeys(speaker_list))  # 保持顺序去重

    @property
    def all_text(self) -> str:
        """获取所有有效句子的合并文本"""
        return ' '.join([item.cleaned_sentence for item in self.valid_sentences])

    def get_sentences_by_speaker(self, speaker: str) -> List[str]:
        """获取指定说话人的所有句子"""
        return [
            item.cleaned_sentence
            for item in self.valid_sentences
            if item.speaker == speaker
        ]


class TranslationTextRequest(BaseModel):
    meetingId: str
    otherMeetingId: str
    translateText: Union[str, Dict[str, Any], TranslateTextContent]
    speakerName: Union[str, None] = None  # 允许为 None

    @validator('translateText', pre=True)
    def parse_translate_text(cls, v):
        """将字符串类型的translateText解析为字典"""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return v  # 如果解析失败，返回原字符串
        return v
    @validator("speakerName", pre=True, always=True)
    def set_default_speaker(cls, v):
        # 如果 v 是 None 或空字符串，返回默认值
        if v is None or v.strip() == "":
            return "未知人员"
        return v



    def get_parsed_translate_text(self) -> TranslateTextContent:
        """获取解析后的translateText内容"""
        if isinstance(self.translateText, str):
            try:
                parsed = json.loads(self.translateText)
            except json.JSONDecodeError:
                # 如果解析失败，返回空的TranslateTextContent
                return TranslateTextContent()
        else:
            parsed = self.translateText

        # 转换为强类型模型
        return TranslateTextContent(**parsed)

    def extract_conversation_data(self) -> Dict[str, Any]:
        """提取完整的对话数据"""
        content = self.get_parsed_translate_text()

        # 按说话人分组
        conversation_by_speaker = {}
        for speaker in content.speakers:
            conversation_by_speaker[speaker] = content.get_sentences_by_speaker(speaker)

        return {
            "meeting_id": self.meetingId,
            "speaker_name": self.speakerName,
            "speakers": content.speakers,
            "total_sentences": len(content.completedSentences),
            "valid_sentences": len(content.valid_sentences),
            "conversation_by_speaker": conversation_by_speaker,
            "full_text": content.all_text,
            "sentences_detail": [
                {
                    "original": item.sentence,
                    "cleaned": item.cleaned_sentence,
                    "speaker": item.speaker,
                    "has_content": item.has_content,
                    "progressive": item.progressive
                }
                for item in content.completedSentences
            ]
        }


class TranscriptionTextResponse(BaseModel):  # 响应模型用Pydantic
    class Config:
        orm_mode = True  # 支持从ORM对象转换