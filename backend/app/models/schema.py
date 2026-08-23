"""
Bounded FaceParameters schema.

Every enum field is nullable until the witness states it, and paired with a
`<field>_verbatim` string capturing the witness's own words for that
feature. The pairing is the "verified information vs. AI-generated
interpretation" separation the spec asks for -- structural, not a disclaimer
bolted onto the UI. Keeping the enum set closed (rather than free-text) is
what keeps composite generation controllable turn over turn: an image model
asked to "make the nose a bit smaller" on free text drifts; asked to render
`nose_size=small` from a fixed vocabulary, it doesn't.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FaceShape(str, Enum):
    oval = "oval"
    round = "round"
    square = "square"
    heart = "heart"
    long = "long"
    diamond = "diamond"


class EyeShape(str, Enum):
    almond = "almond"
    round = "round"
    hooded = "hooded"
    monolid = "monolid"
    downturned = "downturned"
    upturned = "upturned"


class Spacing(str, Enum):
    close_set = "close-set"
    average = "average"
    wide_set = "wide-set"


class Thickness(str, Enum):
    thin = "thin"
    medium = "medium"
    thick = "thick"


class NoseSize(str, Enum):
    small = "small"
    medium = "medium"
    large = "large"


class NoseShape(str, Enum):
    straight = "straight"
    hooked = "hooked"
    upturned = "upturned"
    wide = "wide"
    narrow = "narrow"


class JawShape(str, Enum):
    pointed = "pointed"
    round = "round"
    square = "square"
    cleft = "cleft"


class HairLength(str, Enum):
    bald = "bald"
    short = "short"
    medium = "medium"
    long = "long"


class HairTexture(str, Enum):
    straight = "straight"
    wavy = "wavy"
    curly = "curly"
    coily = "coily"


class FacialHair(str, Enum):
    none = "none"
    stubble = "stubble"
    mustache = "mustache"
    beard = "beard"
    goatee = "goatee"


class FaceParameters(BaseModel):
    """
    A single locked/proposed description of a face. Every `<field>` /
    `<field>_verbatim` pair is deliberately kept adjacent so a serializer
    or UI can never render one without the other next to it.
    """

    face_shape: Optional[FaceShape] = None
    face_shape_verbatim: Optional[str] = None

    eyes_shape: Optional[EyeShape] = None
    eyes_shape_verbatim: Optional[str] = None

    eyes_spacing: Optional[Spacing] = None
    eyes_spacing_verbatim: Optional[str] = None

    eyebrows_thickness: Optional[Thickness] = None
    eyebrows_thickness_verbatim: Optional[str] = None

    nose_size: Optional[NoseSize] = None
    nose_size_verbatim: Optional[str] = None

    nose_shape: Optional[NoseShape] = None
    nose_shape_verbatim: Optional[str] = None

    mouth_width: Optional[Thickness] = None
    mouth_width_verbatim: Optional[str] = None

    jaw_shape: Optional[JawShape] = None
    jaw_shape_verbatim: Optional[str] = None

    hair_length: Optional[HairLength] = None
    hair_length_verbatim: Optional[str] = None

    hair_texture: Optional[HairTexture] = None
    hair_texture_verbatim: Optional[str] = None

    hair_color: Optional[str] = None  # free text: color naming doesn't benefit from a closed enum
    hair_color_verbatim: Optional[str] = None

    facial_hair: Optional[FacialHair] = None
    facial_hair_verbatim: Optional[str] = None

    distinguishing_marks: list[str] = Field(default_factory=list)  # e.g. "scar above left eyebrow"

    def filled_fields(self) -> list[str]:
        return [
            name
            for name in self.model_fields
            if not name.endswith("_verbatim")
            and name != "distinguishing_marks"
            and getattr(self, name) is not None
        ]

    def missing_fields(self) -> list[str]:
        all_enum_fields = [
            name
            for name in self.model_fields
            if not name.endswith("_verbatim") and name != "distinguishing_marks"
        ]
        filled = set(self.filled_fields())
        return [name for name in all_enum_fields if name not in filled]

    def is_complete_enough_for_signoff(self, min_filled: int = 8) -> bool:
        return len(self.filled_fields()) >= min_filled


class FeatureDelta(BaseModel):
    """What the Extraction Agent returns each turn: only the fields the
    witness actually addressed, never a full FaceParameters guess."""

    updates: FaceParameters = Field(default_factory=FaceParameters)
    raw_utterance: str
