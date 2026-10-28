"""Swedish/English equivalence groups for testing and IT terms.

Each group lists variants of one concept. A job-ad keyword that equals any exact variant is
counted in the CV via *all* variants of its group, so a Swedish CV can match an English ad
(and the reverse).

Variant syntax:
  ``"test automation"``   exact word or phrase (plural ``s`` is folded as usual)
  ``"agil*"``             any longer word that starts with ``agil`` (agilitet, agilt, ...)
  ``"*testare"``          any longer word that ends with ``testare`` (mjukvarutestare, ...)
  ``"test+"``             the stem plus a Swedish/English ending from ``INFLECTIONS``
                          (test, testet, tester, testning, testare, testing, tested, ...)

Prefix/suffix variants only count compound words, never the bare word, and are not used to
find the group of a job-ad keyword. Inflected (``+``) variants are used on both sides. Keep
suffixes specific: ``*test`` would match "attest".
"""

from __future__ import annotations

# Endings that may follow an inflected stem. Deliberately short; "testimony" must not match "test+".
INFLECTIONS = (
    "",
    "a",
    "e",
    "n",
    "t",
    "s",
    "en",
    "et",
    "er",
    "ar",
    "or",
    "na",
    "ed",
    "ing",
    "ings",
    "erna",
    "arna",
    "orna",
    "ning",
    "ningen",
    "ningar",
    "are",
    "aren",
    "ade",
    "at",
    "ad",
    "ande",
    "ens",
    "ets",
)

ALIAS_GROUPS: tuple[tuple[str, ...], ...] = (
    # testing in general
    ("test+", "*testare", "*testning", "*testing"),
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
    ("quality", "kvalitet+"),
    ("bug", "bugs", "defect", "defects", "bugg", "buggar", "defekt", "defekter"),
    # ways of working
    ("agile", "agil+", "agila metoder", "agil*"),
    (
        "cross functional",
        "cross-functional",
        "tvärfunktionell",
        "tvärfunktionella",
        "tvärfunktionell*",
    ),
    ("project", "projects", "projekt+"),
    ("stakeholder", "stakeholders", "intressent", "intressenter"),
    ("communication", "kommunikation", "kommunikations*"),
    ("documentation", "dokumentation+"),
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
    ("database", "databases", "databas+"),
)
