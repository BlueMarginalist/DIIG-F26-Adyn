"""Registry of analysis modules. Add a module here and the build picks it up."""
from .biomarkers import Biomarkers
from .funnel import Funnel
from .prescriptions import Prescriptions
from .virtual_care import VirtualCare

ALL_MODULES = {m.name: m for m in (VirtualCare, Biomarkers, Prescriptions, Funnel)}

__all__ = ["ALL_MODULES", "Biomarkers", "Funnel", "Prescriptions", "VirtualCare"]
