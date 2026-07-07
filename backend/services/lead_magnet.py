"""Лид-магнит «Чеклист: 12 проверок участка перед торгами» — генерация PDF.

PDF собирается из HTML через xhtml2pdf (уже в зависимостях). Контент статичен,
поэтому байты PDF кэшируются в модуле — генерим один раз на процесс.
"""
from __future__ import annotations

import io

from core.config import settings

SITE = settings.SITE_URL

# (заголовок проверки, что именно смотреть)
CHECKS = [
    ("ВРИ соответствует вашей цели",
     "Название лота — маркетинг, ВРИ — закон. Под ИЖС нужен ВРИ «для индивидуального "
     "жилищного строительства», а не «для садоводства» или «сельхозиспользование». "
     "Смена ВРИ после покупки — решение муниципалитета через ПЗЗ, без гарантий."),
    ("Категория земель",
     "«Земли населённых пунктов» — самые ликвидные. «Сельхозназначения» — под КФХ и "
     "частично ИЖС (ст. 39.18 ЗК РФ). «Промышленности» — только коммерция. Категория и "
     "ВРИ — разные параметры, проверяйте оба."),
    ("Расхождение площади: извещение против ЕГРН",
     "Сверьте площадь в извещении с кадастровой выпиской. Разница больше 5% — запросите "
     "уточнение у организатора ДО внесения задатка."),
    ("ЗОУИТ и обременения",
     "По публичной кадастровой карте проверьте охранные зоны (ЛЭП, газопровод, водоём), "
     "сервитуты, особые условия использования. Они могут запрещать стройку на части или "
     "всём участке."),
    ("Кадастровая стоимость против начальной цены",
     "Начальная цена сильно ниже кадастровой — повод разобраться почему (неликвид, "
     "обременения), а не только обрадоваться. Для аренды смотрите % выкупа по региону."),
    ("Проект договора: срок и возможность выкупа",
     "Для аренды — на сколько лет и есть ли право выкупа (ст. 39.3, 39.18 ЗК РФ). От срока "
     "зависит и право на переуступку без согласия (см. пункт 7)."),
    ("Переуступка и субаренда",
     "По ст. 22 ЗК РФ при аренде на срок 5+ лет переуступка и субаренда возможны в "
     "уведомительном порядке, без согласия арендодателя. НО проект договора может это "
     "прямо запрещать — проверьте текст, если планируете выход через перепродажу прав."),
    ("Технические условия (ТУ)",
     "Возможность и стоимость подключения электричества, газа, воды. Отсутствие ТУ или "
     "ценник на подключение в миллионы рублей превращает «дешёвый» участок в убыточный."),
    ("Доступ к участку",
     "Есть ли дорога и легальный проезд. «Запертый» участок без доступа через чужие земли — "
     "частая и трудноисправимая проблема."),
    ("Задаток: сумма, сроки, возврат",
     "Задаток должен быть ЗАЧИСЛЕН на счёт организатора до окончания приёма заявок, а не "
     "отправлен в последний день. Проверьте условия и сроки возврата проигравшим."),
    ("Ликвидность: город, рельеф, подтопление",
     "Расстояние до ближайшего города и его население определяют спрос при перепродаже. "
     "Низина, подтопление, крутой рельеф — скрытые затраты на освоение."),
    ("Форма торгов и история цены",
     "Аукцион (цена вверх) или публичное предложение (цена вниз). При повторных торгах "
     "смотрите историю снижения — иногда выгоднее дождаться следующего шага."),
]


def _build_html() -> str:
    items = "".join(
        f"""
        <table class="check"><tr>
          <td class="num">{i}</td>
          <td class="body">
            <div class="ct">{title}</div>
            <div class="cd">{desc}</div>
          </td>
        </tr></table>
        """
        for i, (title, desc) in enumerate(CHECKS, 1)
    )
    # Превью-список на обложке — только заголовки, в 2 колонки. Без него
    # страница 1 = шапка + абзац и выглядит пустой (xhtml2pdf рвёт пагинацию
    # непредсказуемо на table-блоках, оставляя низ страницы 1 голым).
    half = (len(CHECKS) + 1) // 2
    preview_col1 = "".join(
        f'<tr><td class="pn">{i}</td><td class="pt">{title}</td></tr>'
        for i, (title, _desc) in enumerate(CHECKS[:half], 1)
    )
    preview_col2 = "".join(
        f'<tr><td class="pn">{i}</td><td class="pt">{title}</td></tr>'
        for i, (title, _desc) in enumerate(CHECKS[half:], half + 1)
    )
    # DejaVuSans — единственный надёжно кириллический TTF в контейнере; без него
    # встроенный Helvetica (AFM) рендерит русский текст пустыми квадратами.
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
@font-face {{ font-family: "DejaVu"; src: url("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"); }}
@font-face {{ font-family: "DejaVu"; font-weight: bold; src: url("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"); }}
@page {{ size: A4; margin: 1.6cm 1.4cm; }}
body {{ font-family: "DejaVu", sans-serif; color: #1f2937; font-size: 10.5pt; }}
.head {{ background: #0d9488; color: #ffffff; padding: 22pt 18pt; border-radius: 8pt; margin-bottom: 16pt; }}
.head h1 {{ margin: 0; font-size: 22pt; }}
.head p {{ margin: 8pt 0 0; font-size: 11pt; }}
.intro {{ font-size: 11pt; color: #374151; margin: 0 0 16pt; line-height: 1.5; }}
.preview-title {{ font-size: 10pt; font-weight: bold; color: #0d9488; text-transform: uppercase;
  letter-spacing: 0.5pt; margin: 0 0 8pt; }}
.preview {{ width: 100%; border-collapse: collapse; margin-bottom: 18pt; }}
.preview td {{ vertical-align: top; width: 50%; padding: 0 10pt 0 0; }}
.preview table {{ width: 100%; }}
.pn {{ width: 18pt; color: #0d9488; font-weight: bold; font-size: 10pt; padding: 4pt 4pt 4pt 0; vertical-align: top; }}
.pt {{ font-size: 9.5pt; color: #1f2937; padding: 4pt 0; line-height: 1.35; vertical-align: top; }}
.cta-box {{ background: #f0fdfa; border: 1pt solid #99f6e4; border-radius: 8pt; padding: 12pt 14pt;
  font-size: 9.5pt; color: #0f766e; line-height: 1.5; }}
.cta-box a {{ color: #0d9488; font-weight: bold; text-decoration: none; }}
.detail-head {{ font-size: 13pt; font-weight: bold; color: #0d9488; margin: 18pt 0 12pt;
  -pdf-keep-with-next: true; }}
.check {{ width: 100%; margin-bottom: 9pt; -pdf-keep-with-next: true; }}
.num {{ width: 26pt; color: #0d9488; font-size: 15pt; font-weight: bold; vertical-align: top; }}
.body {{ vertical-align: top; }}
.ct {{ font-size: 11.5pt; font-weight: bold; margin-bottom: 2pt; }}
.cd {{ font-size: 9.5pt; color: #4b5563; line-height: 1.4; }}
.foot {{ margin-top: 10pt; padding-top: 8pt; border-top: 1pt solid #e5e7eb; font-size: 9pt; color: #6b7280; }}
.foot a {{ color: #0d9488; text-decoration: none; }}
</style></head>
<body>
  <div class="head">
    <h1>12 проверок участка перед торгами</h1>
    <p>Чеклист от Земля.ОНЛАЙН — torgi-zemli.ru</p>
  </div>
  <p class="intro">
    Пройдите эти 12 пунктов по каждому лоту до внесения задатка. Большинство дорогих
    ошибок на земельных торгах — это пропущенный пункт из списка ниже. Подробный
    разбор каждого пункта — на следующих страницах.
  </p>
  <div class="preview-title">Что внутри</div>
  <table class="preview"><tr>
    <td><table>{preview_col1}</table></td>
    <td><table>{preview_col2}</table></td>
  </tr></table>
  <div class="cta-box">
    Не хотите проверять вручную? AI-аудит на <a href="{SITE}">{SITE.replace('https://', '')}</a>
    разбирает все 12 пунктов по любому лоту с torgi.gov за 5 минут и готовит PDF-отчёт.
  </div>
  <div class="detail-head">Подробный разбор</div>
  {items}
  <div class="foot">
    Полный AI-разбор любого лота с torgi.gov за 5 минут — на
    <a href="{SITE}">{SITE.replace('https://', '')}</a>.
    AI проверяет все 12 пунктов автоматически и готовит PDF-отчёт.
  </div>
</body></html>"""


_PDF_CACHE: bytes | None = None


def get_checklist_pdf() -> bytes:
    """Возвращает байты PDF-чеклиста (генерится один раз на процесс)."""
    global _PDF_CACHE
    if _PDF_CACHE is None:
        from xhtml2pdf import pisa

        buf = io.BytesIO()
        result = pisa.CreatePDF(_build_html(), dest=buf, encoding="utf-8")
        if result.err:
            raise RuntimeError("Не удалось сгенерировать PDF чеклиста")
        _PDF_CACHE = buf.getvalue()
    return _PDF_CACHE
