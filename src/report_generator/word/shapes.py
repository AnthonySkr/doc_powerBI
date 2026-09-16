"""
Repères numérotés à faire glisser sur une image.

Sous chaque capture de visuel, un tableau numérote les champs affichés — et ces
numéros n'ont de sens qu'une fois reportés sur l'image. Le script dessine donc
les pastilles lui-même, alignées sous l'emplacement : il ne reste qu'à les
attraper à la souris et à les déposer au bon endroit.

Ce sont des formes **flottantes** (`wrapNone`, `allowOverlap`) : elles se
posent par-dessus l'image sans déplacer une ligne du document, et les flèches
du clavier les ajustent au pixel près.

Deux écritures de la même forme, comme Word le fait : la moderne (`wps`, Word
2010 et plus) et, en repli, la forme héritée (VML).
"""

import math
from dataclasses import dataclass

from docx.oxml import parse_xml
from docx.oxml.ns import qn
from docx.shared import Emu, Pt

# Espaces de noms nécessaires à la forme, déclarés sur le fragment lui-même.
_NAMESPACES = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "v": "urn:schemas-microsoft-com:vml",
}
_DECLARATIONS = " ".join(f'xmlns:{prefix}="{uri}"' for prefix, uri in _NAMESPACES.items())

# Rang d'empilement des formes : au-dessus du texte et des images du document.
_Z_ORDER = 251658240

_EMU_PER_POINT = 12700


@dataclass(frozen=True)
class MarkerStyle:
    """
    Aspect et disposition d'une rangée de repères, tels que le plan les déclare.

    Les longueurs sont déjà en EMU : `rendering.image_placeholder` les exprime
    en centimètres, et la conversion revient à qui lit le plan.
    """

    size: Emu
    spacing: Emu
    line: Emu
    per_row: int
    shape: str
    fill: str
    text_color: str
    font_size: Pt


def draw_row(paragraph, labels: list[str], style: MarkerStyle, first_id: int) -> int:
    """
    Pose une rangée de repères sur le paragraphe, repliée au-delà de `per_row`.

    Returns:
        Le dernier identifiant de forme employé. Word refuse deux formes de
        même identifiant : la rangée suivante reprend au-dessus.
    """
    # Les repères flottent : sans hauteur réservée, ils déborderaient sur ce
    # qui suit la capture. Le paragraphe porte donc celle de leurs rangées.
    rows = math.ceil(len(labels) / style.per_row)
    paragraph.paragraph_format.line_spacing = Emu(int(style.line) * rows)
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)

    shape_id = first_id
    for label, (left, top) in zip(labels, _positions(len(labels), style), strict=True):
        shape_id += 1
        paragraph._p.append(_marker(label, shape_id, left, top, style))
    return shape_id


def _marker(label: str, shape_id: int, left: Emu, top: Emu, style: MarkerStyle):
    """Une pastille numérotée, flottante, posée à `left`/`top` du paragraphe."""
    return parse_xml(
        _RUN.format(
            declarations=_DECLARATIONS,
            label=_escape(label),
            shape_id=shape_id,
            name=f"Repere {_escape(label)}",
            left=int(left),
            top=int(top),
            size=int(style.size),
            left_pt=round(int(left) / _EMU_PER_POINT, 2),
            top_pt=round(int(top) / _EMU_PER_POINT, 2),
            size_pt=round(int(style.size) / _EMU_PER_POINT, 2),
            z_order=_Z_ORDER + shape_id,
            shape=style.shape,
            vml_shape="oval" if style.shape == "ellipse" else "roundrect",
            fill=style.fill,
            text_color=style.text_color,
            half_points=int(style.font_size.pt * 2),
        )
    )


def last_id(doc) -> int:
    """
    Plus grand identifiant de forme déjà présent dans le document.

    Deux `wp:docPr` de même `id` font signaler à Word un document illisible :
    les repères se numérotent au-dessus de ce que le template porte déjà.
    """
    ids = [
        int(element.get("id") or 0)
        for element in doc.element.body.iter(qn("wp:docPr"))
        if (element.get("id") or "").isdigit()
    ]
    return max(ids, default=0)


def _positions(count: int, style: MarkerStyle) -> list[tuple[Emu, Emu]]:
    """Décalages de chaque repère par rapport au début du paragraphe."""
    return [
        (
            Emu(int(style.spacing) * (rank % style.per_row)),
            Emu(int(style.line) * (rank // style.per_row)),
        )
        for rank in range(count)
    ]


def _escape(value: str) -> str:
    """Échappe ce qui irait dans un fragment XML."""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# Le texte de la pastille : un paragraphe centré, sans espacement, dans les
# deux écritures de la forme.
_LABEL = """
<w:p>
  <w:pPr>
    <w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>
    <w:jc w:val="center"/>
  </w:pPr>
  <w:r>
    <w:rPr><w:b/><w:color w:val="{text_color}"/><w:sz w:val="{half_points}"/></w:rPr>
    <w:t>{label}</w:t>
  </w:r>
</w:p>
"""

_RUN = (
    """
<w:r {declarations}>
  <mc:AlternateContent>
    <mc:Choice Requires="wps">
      <w:drawing>
        <wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0"
                   relativeHeight="{z_order}" behindDoc="0" locked="0"
                   layoutInCell="1" allowOverlap="1">
          <wp:simplePos x="0" y="0"/>
          <wp:positionH relativeFrom="column"><wp:posOffset>{left}</wp:posOffset></wp:positionH>
          <wp:positionV relativeFrom="paragraph"><wp:posOffset>{top}</wp:posOffset></wp:positionV>
          <wp:extent cx="{size}" cy="{size}"/>
          <wp:effectExtent l="0" t="0" r="0" b="0"/>
          <wp:wrapNone/>
          <wp:docPr id="{shape_id}" name="{name}"/>
          <wp:cNvGraphicFramePr/>
          <a:graphic>
            <a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">
              <wps:wsp>
                <wps:cNvSpPr txBox="1"/>
                <wps:spPr>
                  <a:xfrm><a:off x="0" y="0"/><a:ext cx="{size}" cy="{size}"/></a:xfrm>
                  <a:prstGeom prst="{shape}"><a:avLst/></a:prstGeom>
                  <a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>
                  <a:ln w="19050"><a:solidFill><a:srgbClr val="{text_color}"/></a:solidFill></a:ln>
                </wps:spPr>
                <wps:txbx><w:txbxContent>"""
    + _LABEL
    + """</w:txbxContent></wps:txbx>
                <wps:bodyPr rot="0" spcFirstLastPara="0" vertOverflow="overflow"
                            horzOverflow="overflow" vert="horz" wrap="square"
                            lIns="0" tIns="0" rIns="0" bIns="0" anchor="ctr"
                            anchorCtr="0" upright="1"><a:noAutofit/></wps:bodyPr>
              </wps:wsp>
            </a:graphicData>
          </a:graphic>
        </wp:anchor>
      </w:drawing>
    </mc:Choice>
    <mc:Fallback>
      <w:pict>
        <v:{vml_shape} id="repere{shape_id}" fillcolor="#{fill}" strokecolor="#{text_color}"
             strokeweight="1.5pt"
             style="position:absolute;margin-left:{left_pt}pt;margin-top:{top_pt}pt;"""
    + """width:{size_pt}pt;height:{size_pt}pt;z-index:{z_order}">
          <v:textbox inset="0,0,0,0"><w:txbxContent>"""
    + _LABEL
    + """</w:txbxContent></v:textbox>
        </v:{vml_shape}>
      </w:pict>
    </mc:Fallback>
  </mc:AlternateContent>
</w:r>
"""
)
