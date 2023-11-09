import strawberry
import typing
import datetime

from typing import Annotated
from utils.Dataloaders import getLoadersFromInfo, getUserFromInfo

SectionGQLModel = Annotated["SectionGQLModel", strawberry.lazy(".SectionGQLModel")]
FormTypeGQLModel = Annotated["FormTypeGQLModel", strawberry.lazy(".FormTypeGQLModel")]
UserGQLModel = Annotated["UserGQLModel", strawberry.lazy(".externals")]


@strawberry.federation.type(
    keys=["id"], description="""Entity representing a form, form is digitalized A4 sheet"""
)
class FormGQLModel:
    """
    Type representing a request in the system.
    This class extends the base `RequestModel` from the database and adds additional fields and methods needed for use in GraphQL.
    """
    @classmethod
    async def resolve_reference(cls, info: strawberry.types.Info, id: strawberry.ID):
        loader = getLoadersFromInfo(info).forms
        result = await loader.load(id)
        if result is not None:
            result._type_definition = cls._type_definition  # little hack :)
        return result

    @strawberry.field(description="""Entity primary key""")
    def id(self) -> strawberry.ID:
        return self.id

    @strawberry.field(description="""Request's name (like Vacation)""")
    def name(self) -> str:
        return self.name

    @strawberry.field(description="""Request's name (like Vacation)""")
    def name_en(self) -> str:
        return self.name_en

    @strawberry.field(description="""Request's time of last update""")
    def lastchange(self) -> datetime.datetime:
        return self.lastchange

    @strawberry.field(description="""Request's validity""")
    def valid(self) -> bool:
        return self.valid

    @strawberry.field(description="""Request's status""")
    def status(self) -> bool:
        return self.status

    @strawberry.field(description="Retrieves the sections related to this form (form has several sections)")
    async def sections(
        self, info: strawberry.types.Info
    ) -> typing.List["SectionGQLModel"]:
        loader = getLoadersFromInfo(info).sections
        sections = await loader.filter_by(form_id=self.id)
        return sections

    # @strawberry.field(description="Retrieves the user who has initiated this request")
    # async def creator(self, info: strawberry.types.Info) -> "UserGQLModel":
    #     #user = UserGQLModel(id=self.createdby)
    #     from .externals import UserGQLModel
    #     return await UserGQLModel.resolve_reference(id=self.createdby)

    @strawberry.field(description="Retrieves the type of form")
    async def type(self, info: strawberry.types.Info) -> typing.Optional["FormTypeGQLModel"]:
        result = await FormTypeGQLModel.resolve_reference(info, id=self.type_id)
        return result
  

@strawberry.field(description="Retrieves the form type")
async def form_by_id(
    self, info: strawberry.types.Info, id: strawberry.ID
) -> typing.Optional[FormGQLModel]:
    result = await FormGQLModel.resolve_reference(info=info, id=id)
    return result

@strawberry.field(description="Retrieves the form type")
async def form_page(
    self, info: strawberry.types.Info, skip: int = 0, limit: int = 10
) -> typing.List[FormGQLModel]:
    loader = getLoadersFromInfo(info).forms
    result = await loader.page(skip, limit)
    return result    













@strawberry.input
class FormInsertGQLModel:
    name: str
    
    id: typing.Optional[strawberry.ID] = None
    form_type_id: typing.Optional[strawberry.ID] = None
    place: typing.Optional[str] = ""
    published_date: typing.Optional[datetime.datetime] = datetime.datetime.now()
    reference: typing.Optional[str] = ""
    valid: typing.Optional[bool] = True

@strawberry.input
class FormUpdateGQLModel:
    lastchange: datetime.datetime
    id: strawberry.ID

    name: typing.Optional[str] = None
    form_type_id: typing.Optional[strawberry.ID] = None
    place: typing.Optional[str] = None
    published_date: typing.Optional[datetime.datetime] = None
    reference: typing.Optional[str] = None
    valid: typing.Optional[bool] = None
    
    
@strawberry.type
class FormResultGQLModel:
    id: strawberry.ID = None
    msg: str = None

    @strawberry.field(description="""Result of form operation""")
    async def form(self, info: strawberry.types.Info) -> typing.Optional[FormGQLModel]:
        result = await FormGQLModel.resolve_reference(info, self.id)
        return result
   

@strawberry.mutation
async def form_insert(self, info: strawberry.types.Info, form: FormInsertGQLModel) -> FormResultGQLModel:
    loader = getLoadersFromInfo(info).forms
    row = await loader.insert(form)
    result = FormResultGQLModel()
    result.msg = "ok"
    result.id = row.id
    return result

@strawberry.mutation
async def form_update(self, info: strawberry.types.Info, form: FormUpdateGQLModel) -> FormResultGQLModel:
    loader = getLoadersFromInfo(info).forms
    row = await loader.update(form)
    result = FormResultGQLModel()
    result.msg = "ok"
    result.id = form.id
    if row is None:
        result.msg = "fail"
        
    return result   