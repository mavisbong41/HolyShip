import math
import pytest
from backend.app.classification.models import ClassificationInput
from backend.app.classification.pipeline import classify_email
from backend.app.classification.stage2 import Stage2Result

class Resolver:
    def __init__(self, result): self.result=result; self.calls=0
    def resolve(self, **kwargs): self.calls+=1; return self.result

def ambiguous(): return ClassificationInput("x","Invoice","Please compare SI and BL and clarify invoice charges.",[],0)

@pytest.mark.req("CLS-03")
def test_obvious_stage1_bypasses_stage2():
    spy=Resolver(None)
    result=classify_email(ClassificationInput("x","","Please compare the attached SI and draft BL. Verify draft BL.",["SI.txt","BL.txt"],2), stage2_resolver=spy)
    assert result.category=="document_comparison" and spy.calls==0

@pytest.mark.req("CLS-04")
@pytest.mark.req("SCP-05")
@pytest.mark.parametrize("category,confidence,reason", [("invalid",.5,"x"),("invoice_query",-.1,"x"),("invoice_query",1.1,"x"),("invoice_query",math.nan,"x"),("invoice_query",math.inf,"x"),("invoice_query",-math.inf,"x"),("invoice_query",.5,"")])
def test_stage2_rejects_malformed_output(category,confidence,reason):
    resolver=Resolver(Stage2Result(True,category,confidence,{"invoice_query":.5},"reason",False,reason_code=reason))
    with pytest.raises(ValueError): classify_email(ambiguous(),stage2_resolver=resolver)
    assert resolver.calls==1

@pytest.mark.req("CLS-04")
def test_stage2_valid_output_is_used():
    resolver=Resolver(Stage2Result(True,"invoice_query",.8,{"invoice_query":.8},"reason",False,reason_code="TEST"))
    result=classify_email(ambiguous(),stage2_resolver=resolver)
    assert resolver.calls==1 and result.category=="invoice_query" and result.confidence==.8
