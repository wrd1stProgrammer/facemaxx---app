from pydantic import BaseModel, ConfigDict


class FacemaxxBaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

