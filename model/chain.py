from sqlmodel import Field, Relationship, SQLModel


class ChainOut(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    slug: str = Field(unique=True, index=True)


class Chain(ChainOut, table=True):
    __tablename__ = "chains"
    tokens: list["TokenAddress"] = Relationship(back_populates="chain")
