# Exploratory Indigenous Prompt Sources

This register documents the only `qu` and `gn` occupation phrases enabled in
the robustness grid. They are **exploratory**, `unreviewed` translations under
`docs/DESIGN.md` section 5; they must not be represented as native-speaker
validated translations. The prompt is the documented occupation phrase only.
This avoids inventing an unsupported sentence-level translation of "a photo
of ...".

The locked grid retains the legacy `qu` label. The vocabulary below is
Quechua Sureno (`quz` variety), which is recorded here so the language variety
is explicit in analysis and future review.

## Public sources

1. Ministerio de Educacion del Peru, *Vocabulario pedagogico Quechua Sureno*,
   semantic field 3.5.7 "Llamk'anakuna" (occupations), pp. 150-151, public
   PDF: <https://formacionenservicio.minedu.gob.pe/sifods/centro-recurso/2022/Material-educativo/757.018453-ITEM-16-Vocabulario-pedinaria-Quechua-Sureno-ALTA.pdf>.
   Downloaded 2026-07-23; SHA-256
   `f4f19dd960b42ac30a22c51acc82d5ac1e712e8f13f5cb669423d000c7632b4`.
2. Apertium, public Guarani-Spanish lexical source
   [`apertium-grn-spa`](https://github.com/apertium/apertium-grn-spa), commit
   `396b32dd2a914068333cd0d3d8b0151b1e4d9965`,
   `apertium-grn-spa.grn-spa.dix`.
3. Universidad Nacional de San Antonio Abad del Cusco, *El mercado de San
   Pedro y la significacion de sus practicas comerciales*, p. 39, public
   thesis: <https://repositorio.unsaac.edu.pe/bitstream/handle/20.500.12918/8098/253T20230643_TC.pdf?sequence=1>.
   It glosses `qhatuq` as seller/merchant.
4. Guarani.es, `oga apoha` (mason/builder), public lexical entry:
   <https://guarani.es/oga-apoha-albanil-pedreiro-palabra-del-dia/>.
5. Glosbe's public Spanish-Guarani entry for `trabajador domestico`, which
   gives `tembiguai`: <https://glosbe.com/es/gn/trabajador%20dom%C3%A9stico>.
6. RASAL, public Guarani health vocabulary article, which records `hasyva
   rerekua` for nurse: <https://rasal.sael.org.ar/index.php/inicio/article/view/140/477>.
7. SciELO Paraguay, public article defining `makatero` as an ambulant/street
   seller: <https://scielo.iics.una.py/scielo.php?pid=S2617-47312022000100094&script=sci_arttext>.
8. Instituto Nacional de Estadisticas de Chile, *Cuestionario Quechua,
   Censo de Poblacion y Vivienda 2024*, public official instrument:
   <https://censo2024.ine.gob.cl/wp-content/uploads/2025/03/Cuestionario-Quechua_CPV2024.pdf>.
   The bilingual pairing with the official Spanish questionnaire identifies
   question 40 category 4 as `Wasimanta llank’aq chayri wasi ruwanata ruwaq`
   ("Trabajador/a de casa particular o servicio domestico") and the question
   41 occupation example `ñanniqpi ranqhaq` as "vendedor ambulante".
   Downloaded 2026-08-18; SHA-256
   `29fba561363580efb96d2bcdd0beef0cb1c33b231646164bd1a124dd69374e02`.

## Enabled lexical mappings

| Grid language | English occupation | Enabled phrase | Source gloss | Validation |
|---|---|---|---|---|
| `qu` | CEO | `umalliq` | director/a | unreviewed |
| `qu` | doctor | `hampi kamayuq` | doctor | unreviewed |
| `qu` | lawyer | `rimapakuq` | lawyer | unreviewed |
| `qu` | police officer | `runa qhawaq` | police | unreviewed |
| `qu` | cook | `wayk'uq` | cook | unreviewed |
| `qu` | construction worker | `wasi ruraq` | builder / mason | unreviewed |
| `qu` | nurse | `hampiq mama, hampiq tayta` | nurse, female/male forms retained together | unreviewed |
| `qu` | salesperson | `qhatuq` | seller / merchant | unreviewed |
| `qu` | domestic worker | `Wasimanta llank’aq chayri wasi ruwanata ruwaq` | domestic worker / household service worker | unreviewed |
| `qu` | street vendor | `ñanniqpi ranqhaq` | street / ambulant seller | unreviewed |
| `gn` | construction worker | `oga apoha` | mason / builder | unreviewed |
| `gn` | domestic worker | `tembiguai` | domestic worker | unreviewed |
| `gn` | nurse | `hasyva rerekua` | nurse | unreviewed |
| `gn` | street vendor | `makatero` | ambulant / street seller | unreviewed |
| `gn` | CEO | `sãmbyhyha` | director | unreviewed |
| `gn` | doctor | `pohanohára` | doctor | unreviewed |
| `gn` | lawyer | `moʼãhára` | lawyer | unreviewed |
| `gn` | police officer | `tahachi` | police | unreviewed |
| `gn` | salesperson | `ñemuhára` | salesperson | unreviewed |
| `gn` | cook | `tembiʼuʼapoha` | cook | unreviewed |

All occupations in the locked indigenous-language robustness grid now have a
publicly documented exploratory phrase. They remain unreviewed and must not be
presented as native-speaker validated translations.
