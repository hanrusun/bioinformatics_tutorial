"""Cure Lab: a tool-agnostic engine for gamified bioinformatics tutorials.

The engine knows nothing about any particular bioinformatics tool. A *pack*
(e.g. ``packs/seurat``) supplies missions, quizzes and notebook pages plus the
Jupyter kernel that runs learner code; an *illness* file supplies the patient
and the trait tree that evolves on every wrong attempt.
"""

__version__ = "0.1.0"
