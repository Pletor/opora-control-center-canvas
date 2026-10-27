import { formatNumber } from "../../studio-model-run/logic/run-view";
import { SPARK_HEIGHT, SPARK_WIDTH, sparkPoints, sparkRange, type Spark } from "../logic/telemetry-view";

/** Krátká historie jedné veličiny (posledních až 60 ticků) jako lomená čára SVG s popiskem a poslední hodnotou.
 * Bez vykonaného ticku řekne, že historie začne krokem. */
export default function Sparkline({ spark }: { spark: Spark }) {
  const { last, max } = sparkRange(spark.values);
  return <figure className="studio-model-telemetry__spark">
    <figcaption className="studio-model-telemetry__spark-head">
      <span>{spark.label}</span>
      <small className="studio-model-telemetry__spark-value">{spark.values.length ? `${formatNumber(last)}${spark.unit} · max ${formatNumber(max)}${spark.unit}` : "zatím bez ticku"}</small>
    </figcaption>
    <svg className="studio-model-telemetry__spark-chart" viewBox={`0 0 ${SPARK_WIDTH} ${SPARK_HEIGHT}`} preserveAspectRatio="none" role="img"
      aria-label={`${spark.label}: historie ${spark.values.length} ticků, výpočet modelu`}>
      {spark.values.length > 0 && <polyline className="studio-model-telemetry__spark-line" points={sparkPoints(spark.values)} style={{ stroke: spark.color }}/>}
    </svg>
  </figure>;
}
