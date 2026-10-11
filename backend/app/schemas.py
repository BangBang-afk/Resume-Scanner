from pydantic import BaseModel, Field


class Evidence(BaseModel):
    quote: str
    confidence: float = Field(ge=0.0, le=1.0)


class SkillMention(BaseModel):
    raw: str
    canonical: str | None = None
    evidence: Evidence | None = None


class Experience(BaseModel):
    title: str | None = None
    org: str | None = None
    start: str | None = None
    end: str | None = None
    years: float | None = None
    summary: str | None = None
    skills: list[str] = []
    evidence: Evidence | None = None


class Project(BaseModel):
    name: str | None = None
    summary: str | None = None
    skills: list[str] = []
    evidence: Evidence | None = None


class Education(BaseModel):
    degree: str | None = None
    field: str | None = None
    institution: str | None = None
    year: int | None = None


class ResumeProfile(BaseModel):
    skills: list[SkillMention] = []
    experience: list[Experience] = []
    projects: list[Project] = []
    education: list[Education] = []
    certifications: list[str] = []
    missing_sections: list[str] = []
    parse_quality: float = Field(ge=0.0, le=1.0)
