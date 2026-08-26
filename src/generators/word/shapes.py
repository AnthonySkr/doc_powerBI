"""
Repères numérotés à faire glisser sur une capture.

Sous chaque capture de visuel, un tableau numérote les champs affichés — et ces
numéros n'ont de sens qu'une fois reportés sur l'image. Jusqu'ici c'était à
faire à la main, en dessinant une pastille par ligne du tableau.

Le script les dessine donc lui-même, alignés sous l'emplacement de la capture :
il ne reste qu'à les attraper à la souris et à les déposer au bon endroit de
l'image. Ce sont des formes **flottantes** (`wrapNone`, `allowOverlap`) : elles
se posent par-dessus la capture sans déplacer une ligne du document, et les
flèches du clavier les ajustent au pixel près.

Deux écritures de la même forme, comme Word le fait lui-même : la moderne
(`wps`, Word 2010 et plus) et, en repli, la forme héritée (VML) pour les
lecteurs qui ne connaissent que celle-là.
"""

from docx.oxml import parse_xml
from docx.oxml.ns import qn
from docx.shared import Cm, Emu, Pt

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


def marker(
    label: str,
    shape_id: int,
    left: Emu,
    top: Emu,
    size: Emu,
    shape: str = "ellipse",
    fill: str = "0070C0",
    text_color: str = "FFFFFF",
    font_size: Pt = Pt(9),
):
    """
    Une pastille numérotée, flottante, posée à `left`/`top` du paragraphe.

    Retourne le `w:r` à ajouter au paragraphe qui la porte. `shape_id` doit
    être unique dans le document : Word refuse deux formes de même identifiant.
    """
    return parse_xml(
        _RUN.format(
            declarations=_DECLARATIONS,
            label=_escape(label),
            shape_id=shape_id,
            name=f"Repere {_escape(label)}",
            left=int(left),
            top=int(top),
            size=int(size),
            left_pt=round(int(left) / _EMU_PER_POINT, 2),
            top_pt=round(int(top) / _EMU_PER_POINT, 2),
            size_pt=round(int(size) / _EMU_PER_POINT, 2),
            z_order=_Z_ORDER + shape_id,
            shape=shape,
            vml_shape="oval" if shape == "ellipse" else "roundrect",
            fill=fill,
            text_color=text_color,
            half_points=int(font_size.pt * 2),
        )
    )


def last_id(doc) -> int:
    """
    Plus grand identifiant de forme déjà présent dans le document.

    Word tient les identifiants de formes pour uniques : deux `wp:docPr` de
    même `id` lui font signaler un document illisible. Les repères se
    numérotent donc au-dessus de ce que le template contient déjà.
    """
    ids = [
        int(element.get("id") or 0)
        for element in doc.element.body.iter(qn("wp:docPr"))
        if (element.get("id") or "").isdigit()
    ]
    return max(ids, default=0)


def row_positions(count: int, spacing: Cm, per_row: int, line: Cm) -> list[tuple[Emu, Emu]]:
    """Positions d'une rangée de repères, repliée au-delà de `per_row`."""
    return [
        (Emu(int(spacing) * (rank % per_row)), Emu(int(line) * (rank // per_row)))
        for rank in range(count)
    ]


def _escape(value: str) -> str:
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
