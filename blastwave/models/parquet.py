"""
Script for converting Pydantic models to PyArrow schemas for Parquet serialization
"""

import pyarrow as pa
from pydantic import BaseModel

PYDANTIC_TO_ARROW = {
    float: pa.float64(),
    int: pa.int64(),
    str: pa.string(),
    bool: pa.bool_(),
}


def pydantic_to_arrow_schema(
    model: type[BaseModel], include_computed: bool = False
) -> pa.Schema:
    """
    Convert a Pydantic model to an Arrow schema

    :param model: BaseModel
    :param include_computed: bool indicating whether to include computed fields
    :return: PyArrow schema
    """
    fields = []

    for name, field in model.model_fields.items():
        annotation = field.annotation
        if annotation is None:
            continue

        args = getattr(annotation, "__args__", None)
        if args:
            annotation = next(a for a in args if not isinstance(a, type(None)))

        arrow_type = PYDANTIC_TO_ARROW.get(annotation, pa.string())
        fields.append(pa.field(name, arrow_type, nullable=True))

    if include_computed:
        for name, computed_field in model.model_computed_fields.items():
            annotation = computed_field.return_type

            if annotation not in PYDANTIC_TO_ARROW:
                continue

            args = getattr(annotation, "__args__", None)
            if args:
                annotation = next(a for a in args if not isinstance(a, type(None)))
            # Skip derived lists etc
            if annotation not in PYDANTIC_TO_ARROW:
                continue
            fields.append(pa.field(name, PYDANTIC_TO_ARROW[annotation], nullable=True))

    return pa.schema(fields)
