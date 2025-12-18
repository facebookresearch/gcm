import clsx from 'clsx';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

const FeatureList = [
  {
    title: 'GCM Health Checks',
    // Svg: require('@site/static/img/undraw_docusaurus_mountain.svg').default,
    description: (
      <>
        Comprehensive validation suite for GPU clusters. Verify system health,
        hardware functionality, network connectivity, and configuration correctness
        across compute nodes.
      </>
    ),
  },
  {
    title: 'GCM Monitoring',
    // Svg: require('@site/static/img/undraw_docusaurus_tree.svg').default,
    description: (
      <>
        Collect and export Slurm job scheduler and GPU (NVML) metrics in a loop.
        Support for multiple exporters including OTLP, Prometheus, and custom sinks.
      </>
    ),
  },
  {
    title: 'GCM GPU Metrics',
    // Svg: require('@site/static/img/undraw_docusaurus_react.svg').default,
    description: (
      <>
        Process and analyze GPU telemetry data from Slurm workloads. Extract insights
        from job performance metrics and resource utilization patterns.
      </>
    ),
  },
];

function Feature({Svg, title, description}) {
  return (
    <div className={clsx('col col--4')}>
      {/* <div className="text--center">
        <Svg className={styles.featureSvg} role="img" />
      </div> */}
      <div className="text--center padding-horiz--md">
        <Heading as="h3">{title}</Heading>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures() {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
