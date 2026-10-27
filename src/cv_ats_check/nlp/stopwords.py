"""Swedish and English stop words plus job-ad boilerplate, and a tiny language guesser."""

from __future__ import annotations

from cv_ats_check.nlp.normalize import tokenize

EN_STOPWORDS = frozenset(
    """a about above after again against all also am an and any are as at be because been before
    being below between both but by can could did do does doing down during each few for from
    further had has have having he her here hers him his how i if in into is it its just me more
    most my no nor not of off on once only or other our ours out over own same she should so some
    such than that the their theirs them then there these they this those through to too under
    until up very was we were what when where which while who whom why will with would you your
    yours etc eg ie via per within across""".split()
)

SV_STOPWORDS = frozenset(
    """och att det som en ett är på för med av inte den de du vi i om till har kan ska vara var
    från men eller så också hade han hon hos mot under över efter innan genom utan vid där här dig
    din ditt dina er ert era sig sin sitt sina vår vårt våra mig min mitt mina oss dem deras hans
    hennes dessa denna detta alla andra annan annat samt både bland mellan sedan redan bara mycket
    mer mest många någon något några inga ingen inget kommer blir bli vill skall får fått finns ha
    göra gör gjort än när hur vad vem varför vilken vilket vilka""".split()
)

# Words that appear in nearly every job ad and say nothing about the candidate.
NOISE_WORDS = frozenset(
    """experience experienced ability able strong good great excellent team teams role company
    work working works looking join offer offers including include well new want need must plus
    years year least preferably required requirements responsibilities opportunity position
    candidate candidates ideal knowledge skills skill understanding using use used based help
    ensure nice build maintain support environment passionate world erfarenhet erfarenheter arbeta arbetar arbete
    arbetet roll rollen företag företaget söker tjänst tjänsten ansök ansökan meriterande goda god
    bra stark starkt kunskap kunskaper förståelse använda användning år minst gärna krav
    kvalifikationer ansvar möjlighet kandidat kandidater uppdrag miljö stöd sätt nya ny nytt""".split()
)

STOPWORDS = EN_STOPWORDS | SV_STOPWORDS | NOISE_WORDS

_SV_MARKERS = frozenset("och att det som är för med av inte på jag vi du har till".split())
_EN_MARKERS = frozenset("the and of to with for is are you we our will have that this".split())


def detect_language(text: str) -> str:
    """Guess 'sv' or 'en' by counting language-exclusive function words."""
    tokens = tokenize(text)
    sv = sum(t in _SV_MARKERS for t in tokens)
    en = sum(t in _EN_MARKERS for t in tokens)
    return "sv" if sv > en else "en"
