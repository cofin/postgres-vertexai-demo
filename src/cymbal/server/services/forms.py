"""Form auto-generation from Pydantic schemas.

Generates HTML forms dynamically from Pydantic models using
litestar-vite JSON templating.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Type, get_args, get_origin

from pydantic import BaseModel


class FieldType(str, Enum):
    """HTML field types."""

    TEXT = "text"
    NUMBER = "number"
    EMAIL = "email"
    PASSWORD = "password"
    TEXTAREA = "textarea"
    SELECT = "select"
    CHECKBOX = "checkbox"
    DATE = "date"
    DATETIME = "datetime-local"
    FILE = "file"
    HIDDEN = "hidden"


@dataclass
class FormField:
    """Represents a form field."""

    name: str
    field_type: FieldType
    label: str
    required: bool = True
    default: Any = None
    placeholder: str = ""
    options: list[dict[str, str]] | None = None
    validation: dict[str, Any] | None = None


@dataclass
class FormSchema:
    """Complete form schema."""

    title: str
    fields: list[FormField]
    method: str = "POST"
    action: str = ""
    submit_label: str = "Submit"


class FormGenerator:
    """Generate forms from Pydantic models.

    Usage:
        generator = FormGenerator()
        schema = generator.from_model(CoffeeChatMessage)
        json_schema = schema.to_json()
    """

    def from_model(self, model_class: Type[BaseModel], title: str | None = None) -> FormSchema:
        """Generate form schema from Pydantic model.

        Args:
            model_class: Pydantic model to convert
            title: Optional form title (defaults to model name)

        Returns:
            FormSchema with all fields
        """
        fields = []

        for field_name, field_info in model_class.model_fields.items():
            form_field = self._convert_field(field_name, field_info)
            if form_field:
                fields.append(form_field)

        return FormSchema(title=title or model_class.__name__, fields=fields)

    def _convert_field(self, name: str, field_info: Any) -> FormField | None:
        """Convert a Pydantic field to FormField.

        Args:
            name: Field name
            field_info: Pydantic field info

        Returns:
            FormField or None if field should be excluded
        """
        annotation = field_info.annotation

        # Skip complex types for now
        if self._is_complex_type(annotation):
            return None

        field_type = self._map_field_type(annotation)

        # Get default value
        default = None
        if not field_info.is_required():
            default = field_info.default

        return FormField(
            name=name,
            field_type=field_type,
            label=self._generate_label(name),
            required=field_info.is_required(),
            default=default,
            placeholder=self._generate_placeholder(name),
        )

    def _map_field_type(self, annotation: Any) -> FieldType:
        """Map Python type to FieldType."""
        # Handle Optional types
        origin = get_origin(annotation)
        if origin is not None:
            args = get_args(annotation)
            if len(args) > 0 and type(None) in args:
                annotation = args[0]

        # Map types
        if annotation == str:
            return FieldType.TEXT
        elif annotation == int or annotation == float:
            return FieldType.NUMBER
        elif annotation == bool:
            return FieldType.CHECKBOX
        elif annotation == date:
            return FieldType.DATE
        elif annotation == datetime:
            return FieldType.DATETIME

        # Default to text
        return FieldType.TEXT

    def _is_complex_type(self, annotation: Any) -> bool:
        """Check if type is too complex for auto-generation."""
        # Skip model fields (classes that inherit from BaseModel)
        try:
            if issubclass(annotation, BaseModel):
                return True
        except TypeError:
            pass

        # Skip complex generics
        origin = get_origin(annotation)
        if origin in (list, dict, set):
            return True

        return False

    def _generate_label(self, field_name: str) -> str:
        """Generate human-readable label from field name."""
        return field_name.replace("_", " ").title()

    def _generate_placeholder(self, field_name: str) -> str:
        """Generate placeholder text."""
        return f"Enter {field_name.replace('_', ' ')}"


def generate_form_json(model_class: Type[BaseModel]) -> dict[str, Any]:
    """Convenience function to generate form JSON from model.

    Args:
        model_class: Pydantic model class

    Returns:
        JSON-serializable form schema
    """
    generator = FormGenerator()
    schema = generator.from_model(model_class)

    return {
        "title": schema.title,
        "method": schema.method,
        "action": schema.action,
        "submit_label": schema.submit_label,
        "fields": [
            {
                "name": f.name,
                "type": f.field_type.value,
                "label": f.label,
                "required": f.required,
                "default": f.default,
                "placeholder": f.placeholder,
            }
            for f in schema.fields
        ],
    }
