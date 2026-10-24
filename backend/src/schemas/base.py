from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class Esquema(BaseModel):
    """JSON en camelCase, como el contrato S04. Campos desconocidos → 422."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )
