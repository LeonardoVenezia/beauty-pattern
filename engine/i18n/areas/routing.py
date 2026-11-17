"""Avisos de las opciones que todavia se aproximan (engine/garments/routing.py)."""

TEXTS: dict[str, dict[str, str]] = {
    "es": {
        "warning.approx.category": "Este tipo de pieza todavía no tiene un cálculo propio: se entrega el patrón verificado de la pieza más parecida. Conviene ajustar la forma a mano.",
        "warning.approx.neckline": "Ese escote todavía no tiene un cálculo propio: se usa el más parecido.",
        "warning.approx.length": "Ese largo todavía no tiene un cálculo propio: se usa el más parecido.",
        "warning.approx.stitch": "Ese punto todavía no tiene un gráfico propio: el patrón usa el más parecido. Las cuentas valen para el punto de la foto si la muestra da la misma densidad.",
        "warning.approx.figure": "Ese animal todavía no tiene una plantilla propia: se entrega un muñeco base para agregarle los detalles.",
        "warning.approx.toy_body": "Esa forma de cuerpo todavía no tiene una plantilla propia: se entrega el juguete en piezas.",
        "warning.approx.motif_shape": "Esa forma de motivo todavía no tiene un cálculo propio: se entrega un motivo redondo.",
    },
    "en": {
        "warning.approx.category": "This type of piece doesn't have its own calculation yet: you get the verified pattern of the closest piece. You may want to adjust the shape by hand.",
        "warning.approx.neckline": "That neckline doesn't have its own calculation yet: the closest one is used.",
        "warning.approx.length": "That length doesn't have its own calculation yet: the closest one is used.",
        "warning.approx.stitch": "That stitch doesn't have its own chart yet: the pattern uses the closest one. The counts hold for the stitch in the photo if your swatch gives the same gauge.",
        "warning.approx.figure": "That animal doesn't have its own template yet: you get a basic doll to add the details to.",
        "warning.approx.toy_body": "That body shape doesn't have its own template yet: the toy is made in pieces.",
        "warning.approx.motif_shape": "That motif shape doesn't have its own calculation yet: you get a round motif.",
    },
    "fr": {
        "warning.approx.category": "Ce type de pièce n'a pas encore de calcul propre\u00a0: vous recevez le modèle vérifié de la pièce la plus proche. Ajustez la forme à la main si besoin.",
        "warning.approx.neckline": "Cette encolure n'a pas encore de calcul propre\u00a0: on utilise la plus proche.",
        "warning.approx.length": "Cette longueur n'a pas encore de calcul propre\u00a0: on utilise la plus proche.",
        "warning.approx.stitch": "Ce point n'a pas encore de grille propre\u00a0: le modèle utilise le plus proche. Les calculs restent valables si votre échantillon donne la même tension.",
        "warning.approx.figure": "Cet animal n'a pas encore de modèle propre\u00a0: vous recevez une poupée de base à compléter.",
        "warning.approx.toy_body": "Cette forme de corps n'a pas encore de modèle propre\u00a0: le jouet est fait en pièces.",
        "warning.approx.motif_shape": "Cette forme de motif n'a pas encore de calcul propre\u00a0: vous recevez un motif rond.",
    },
    "de": {
        "warning.approx.category": "Für diese Art von Teil gibt es noch keine eigene Berechnung: Du bekommst die geprüfte Anleitung des ähnlichsten Teils. Pass die Form bei Bedarf von Hand an.",
        "warning.approx.neckline": "Für diesen Ausschnitt gibt es noch keine eigene Berechnung: Es wird der ähnlichste verwendet.",
        "warning.approx.length": "Für diese Länge gibt es noch keine eigene Berechnung: Es wird die ähnlichste verwendet.",
        "warning.approx.stitch": "Für dieses Muster gibt es noch kein eigenes Diagramm: Die Anleitung verwendet das ähnlichste. Die Zahlen gelten, wenn deine Maschenprobe dieselbe Festigkeit ergibt.",
        "warning.approx.figure": "Für dieses Tier gibt es noch keine eigene Vorlage: Du bekommst eine Grundfigur zum Ergänzen.",
        "warning.approx.toy_body": "Für diese Körperform gibt es noch keine eigene Vorlage: Das Kuscheltier wird in Teilen gearbeitet.",
        "warning.approx.motif_shape": "Für diese Motivform gibt es noch keine eigene Berechnung: Du bekommst ein rundes Motiv.",
    },
    "it": {
        "warning.approx.category": "Questo tipo di pezzo non ha ancora un calcolo proprio: ricevi lo schema verificato del pezzo più simile. Conviene adattare la forma a mano.",
        "warning.approx.neckline": "Questo scollo non ha ancora un calcolo proprio: si usa il più simile.",
        "warning.approx.length": "Questa lunghezza non ha ancora un calcolo proprio: si usa la più simile.",
        "warning.approx.stitch": "Questo punto non ha ancora uno schema proprio: si usa il più simile. I conteggi valgono se il tuo campione dà la stessa tensione.",
        "warning.approx.figure": "Questo animale non ha ancora un modello proprio: ricevi un pupazzo base da completare.",
        "warning.approx.toy_body": "Questa forma di corpo non ha ancora un modello proprio: il pupazzo si fa a pezzi.",
        "warning.approx.motif_shape": "Questa forma di motivo non ha ancora un calcolo proprio: ricevi un motivo rotondo.",
    },
}
