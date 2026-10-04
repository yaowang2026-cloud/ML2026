from enum import Enum
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)


TARGET_FIELDS = (
    "id",
    "age (years)",
    "education level (0=none/primary,1=secondary,2=higher)",
    "consanguinity",
    "desired pregnancy",
    "hypertension history",
    "diabetes mellitus",
    "gravidity (number)",
    "parity (number)",
    "abortions (number)",
    "living children (number)",
    "previous cesarean",
    "bmi pregestational (kg/m2)",
    "mean systolic bp (mmhg)",
    "mean diastolic bp (mmhg)",
    "hemoglobin (g/dl)",
    "first fasting glucose (mg/dl)",
    "proteinuria",
    "hiv test result",
    "syphilis test result",
    "hepatitis c test result",
    "gestational age at enrollment (weeks)",
    "gestational dm",
    "gestational age at birth (weeks)",
    "preterm birth",
    "type of delivery (0=vaginal,1=cesarean)",
    "newborn sex (0=female,1=male)",
    "child birth weight (g)",
    "head circumference (cm)",
    "breastfeeding initiated",
    "referral to higher care",
)

CODING_RULES = {
    "education level (0=none/primary,1=secondary,2=higher)": {
        "none": 0,
        "primary": 0,
        "secondary": 1,
        "higher": 2,
    },
    "type of delivery (0=vaginal,1=cesarean)": {
        "vaginal": 0,
        "cesarean": 1,
    },
    "newborn sex (0=female,1=male)": {
        "female": 0,
        "male": 1,
    },
}

YES_NO_FIELDS = frozenset(
    {
        "consanguinity",
        "desired pregnancy",
        "hypertension history",
        "diabetes mellitus",
        "previous cesarean",
        "proteinuria",
        "gestational dm",
        "preterm birth",
        "breastfeeding initiated",
        "referral to higher care",
    }
)

TEST_RESULT_FIELDS = frozenset(
    {
        "hiv test result",
        "syphilis test result",
        "hepatitis c test result",
    }
)

BINARY_FIELDS = YES_NO_FIELDS | TEST_RESULT_FIELDS | frozenset(
    {
        "type of delivery (0=vaginal,1=cesarean)",
        "newborn sex (0=female,1=male)",
    }
)

NUMERIC_FIELDS = frozenset(
    {
        "age (years)",
        "gravidity (number)",
        "parity (number)",
        "abortions (number)",
        "living children (number)",
        "bmi pregestational (kg/m2)",
        "mean systolic bp (mmhg)",
        "mean diastolic bp (mmhg)",
        "hemoglobin (g/dl)",
        "first fasting glucose (mg/dl)",
        "gestational age at enrollment (weeks)",
        "gestational age at birth (weeks)",
        "child birth weight (g)",
        "head circumference (cm)",
    }
)


class ExtractionStatus(str, Enum):
    KNOWN = "KNOWN"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    ILLEGIBLE = "ILLEGIBLE"
    NOT_PROVIDED = "NOT_PROVIDED"


class ExtractedField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_name: StrictStr = Field(json_schema_extra={"enum": list(TARGET_FIELDS)})
    value: StrictInt | StrictFloat | StrictStr | None
    status: ExtractionStatus
    evidence: StrictStr | None
    reason: StrictStr | None = None
    question: StrictStr | None = None

    @field_validator("field_name")
    @classmethod
    def validate_field_name(cls, value: str) -> str:
        if value not in TARGET_FIELDS:
            raise ValueError(f"Unexpected registry field: {value}")
        return value


class ExtractionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: list[ExtractedField] = Field(
        min_length=len(TARGET_FIELDS),
        max_length=len(TARGET_FIELDS),
    )

    @model_validator(mode="after")
    def validate_exact_field_set(self) -> "ExtractionResponse":
        field_names = [item.field_name for item in self.fields]
        if len(field_names) != len(set(field_names)):
            raise ValueError("Duplicate registry field names returned.")

        missing = set(TARGET_FIELDS) - set(field_names)
        if missing:
            raise ValueError(f"Missing registry fields: {sorted(missing)}")
        return self


class OCRExtractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ocr_text: str = Field(min_length=1, max_length=100_000)

    @model_validator(mode="after")
    def validate_nonblank_ocr(self) -> "OCRExtractionRequest":
        if not self.ocr_text.strip():
            raise ValueError("ocr_text must contain non-whitespace text.")
        return self
