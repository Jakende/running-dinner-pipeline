from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum

class DietType(str, Enum):
    VEGAN = "vegan"
    VEGETARIAN = "vegetarisch"
    OMNIVORE = "alles"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, s: str):
        s = s.lower().strip() if s else ""
        if "vegan" in s:
            return cls.VEGAN
        if "veget" in s:  # covers vegetarisch, vegetarisch/vegan etc.
            return cls.VEGETARIAN
        if "alles" in s or "omni" in s or "flexi" in s:
            return cls.OMNIVORE
        return cls.UNKNOWN

class CourseType(str, Enum):
    STARTER = "starter"
    MAIN = "main"
    DESSERT = "dessert"

@dataclass
class Team:
    id: int
    name1: str
    name2: str
    email1: str
    email2: str
    phone1: str
    phone2: str
    address_street: str
    address_zip: str
    address_city: str
    full_address: str
    latitude: float
    longitude: float
    diet: DietType
    allergies: Dict[str, str]  # e.g., {'gluten': 'Ja', 'nuts': 'Nein'}
    hints: str = ""
    language: str = "de"
    
    @property
    def names(self) -> Tuple[str, str]:
        return (self.name1, self.name2)
    
    @property
    def team_name(self) -> str:
        return f"{self.name1} & {self.name2}"
    
    def get_allergy_list(self) -> List[str]:
        return [k for k, v in self.allergies.items() if v == 'Ja']


@dataclass
class MatchResult:
    course: CourseType
    host_id: int
    guest_ids: List[int]

@dataclass
class DinnerPlan:
    matches: List[MatchResult]
    total_distance: float
    is_valid: bool
