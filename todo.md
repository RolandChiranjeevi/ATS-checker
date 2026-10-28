# Att göra (Johan)

Det här är sakerna som bara du kan göra. Claude tar resten.

## Imorgon

- [ ] **Anonymisera din LaTeX-PDF** och lägg den i `tests/fixtures/` (t.ex. `cv_latex_anonymized.pdf`).
  - Byt ut namn, telefon, e-post, LinkedIn-länk och företagsnamn.
  - Byt också ut **författare och titel** i filens egenskaper (verktyget visar dem).
  - Behåll layout, typsnitt, ikoner och datumformat: det är dem som gör filen till ett bra test.
  - Enklast: ändra värdena i LaTeX-källan och kompilera om (då blir metadatan konsekvent).
  - Säg till när den ligger där, så skriver Claude testerna mot den och tar ligaturerna.

## Snart

- [ ] **Rätta din globala git-e-post** (den har fel id och en punkt på slutet):

  ```bash
  git config --global user.email "148742962+RolandChiranjeevi@users.noreply.github.com"
  ```

- [ ] **Radera säkerhetskopian** när du är nöjd med historiken:

  ```bash
  cd ~/Documents/cv-ats-check && git branch -D backup-before-author-rewrite
  ```

- [ ] **Kolla CI på GitHub** (fliken Actions) när din månadsgräns nollställs. Det har aldrig körts där, så Python 3.11 och 3.12 är obevisade.
- [ ] **Kör ditt riktiga CV mot 2–3 riktiga annonser** i webbvyn och skriv ner det som ser fel ut:
  - falska varningar (t.ex. layout- eller hygienkontrollen)
  - nyckelord som borde ha matchat men hamnar under "Missing"
  - nyckelord som är brus
- [ ] **Prova den nya annonsanalysen** på en riktig annons (se etapp C nedan).

## Beslut

- [ ] Ska repot bli **publikt**? Innan dess:
  - byt `<your-repo-url>` i README mot den riktiga adressen
  - kolla copyright-raden i `LICENSE` (nu "Johan Thylin")
  - läs igenom README en gång till
- [ ] Vill du ha fler **begreppsgrupper** (svenska/engelska) än de cirka 28 som finns? Skriv de termer du ofta ser i annonser, så lägger Claude till dem.

## Etapp C (Claude bygger nu) – det du ska kontrollera efteråt

- [ ] Annonsen delas upp i **krav** och **meriterande**: stämmer uppdelningen på din annons?
- [ ] Raden **Job ad requirements**: hittar den år, språk, arbetssätt (distans/hybrid/på plats) och ort rätt?
- [ ] Är den **viktade poängen** rimlig jämfört med hur du själv bedömer annonsen?
- [ ] Matchar svenska böjningar nu (testning, testare, kvaliteten, projektet ...)?

## Klart

- [x] Etapp A: falska larm rättade, textvy, nedladdning
- [x] Etapp B: layout- och hygienkontroller, klickbara länkar
- [x] Telefonnummer med PDF-tecken
