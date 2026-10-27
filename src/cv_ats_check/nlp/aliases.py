"""Swedish/English equivalence groups for testing and IT terms.

Each group lists variants of one concept. A job-ad keyword that equals any exact variant is
counted in the CV via *all* variants of its group, so a Swedish CV can match an English ad
(and the reverse).

Variant syntax:
  ``"test automation"``   exact word or phrase (plural ``s`` is folded as usual)
  ``"agil*"``             any longer word that starts with ``agil`` (agilitet, agilt, ...)
  ``"*testare"``          any longer word that ends with ``testare`` (mjukvarutestare, ...)

Prefix/suffix variants only count compound words, never the bare word, and are not used to
find the group of a job-ad keyword. Keep suffixes specific: ``*test`` would match "attest".
"""

from __future__ import annotations

ALIAS_GROUPS: tuple[tuple[str, ...], ...] = (
    # testing in general
    ("testing", "test", "testning", "tester", "testare", "*testare", "*testning", "*testing"),
    (
        "test automation",
        "automated testing",
        "automated tests",
        "automated test",
        "testautomatisering",
        "testautomation",
        "automatiserad testning",
        "automatiserade tester",
        "automatisk testning",
        "testautomati*",
    ),
    ("automated", "automatiserad", "automatiserade", "automatiserat", "automatisk", "automatiska"),
    ("manual", "manuell", "manuella", "manuellt"),
    ("manual testing", "manuell testning", "manuella tester", "manuella test"),
    ("test cases", "test case", "testfall", "testfall*"),
    ("test strategy", "teststrategi", "teststrategi*"),
    ("test plan", "testplan", "testplan*"),
    ("test design", "testdesign", "testdesign*"),
    ("regression testing", "regressionstest", "regressionstester", "regressionstest*"),
    (
        "performance testing",
        "prestandatest",
        "prestandatester",
        "prestandatestning",
        "prestandatest*",
    ),
    ("integration testing", "integrationstest", "integrationstester", "integrationstest*"),
    ("acceptance testing", "acceptanstest", "acceptanstester", "acceptanstest*"),
    ("unit testing", "unit tests", "unit test", "enhetstest", "enhetstester", "enhetstest*"),
    ("api testing", "api testning", "api test", "api tester", "api tests"),
    ("exploratory testing", "utforskande testning", "utforskande tester"),
    # quality
    ("quality assurance", "qa", "kvalitetssäkring", "kvalitetskontroll", "kvalitetssäkr*"),
    ("quality", "kvalitet", "kvalitets*"),
    ("bug", "bugs", "defect", "defects", "bugg", "buggar", "defekt", "defekter"),
    # ways of working
    ("agile", "agil", "agila", "agilt", "agila metoder", "agil*"),
    (
        "cross functional",
        "cross-functional",
        "tvärfunktionell",
        "tvärfunktionella",
        "tvärfunktionell*",
    ),
    ("project", "projekt", "projekt*"),
    ("stakeholder", "stakeholders", "intressent", "intressenter"),
    ("communication", "kommunikation", "kommunikations*"),
    ("documentation", "dokumentation", "dokumentation*"),
    # tech
    (
        "software",
        "mjukvara",
        "programvara",
        "*mjukvara",
        "*programvara",
        "mjukvaru*",
        "programvaru*",
    ),
    ("developer", "developers", "utvecklare", "*utvecklare"),
    ("development", "utveckling", "*utveckling"),
    ("database", "databas", "databaser", "databas*"),
)
