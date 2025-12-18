import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import HomepageFeatures from '@site/src/components/HomepageFeatures';
import ThemedImage from '@theme/ThemedImage';

import Heading from '@theme/Heading';
import styles from './index.module.css';

function HomepageHeader() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <header className={clsx('hero hero--primary', styles.heroBanner)}>
      <div className="container">
        <ThemedImage
          alt="GCM Logo"
          sources={{
            light: '/gcm/img/gcm_long_white.svg',
            dark: '/gcm/img/gcm_long_black.svg',
          }}
          style={{maxWidth: '50%', minWidth: '250px'}}
        />
        <p className="hero__subtitle">{siteConfig.tagline}</p>
        <div
          className={styles.buttons}
        >
          <Link
            style={{
              backgroundColor: 'var(--btn-green-bg)',
              borderColor: 'var(--btn-green-bg)',
              color: 'var(--btn-green-text)'
            }}
            className="button button--secondary button--lg"
            to="/docs/getting_started">
            GCM Getting Started
          </Link>
        </div>
        <br/>
        <span className={styles['index-ctas-github-button']}>
          <iframe
            src="https://ghbtns.com/github-btn.html?user=facebookresearch&amp;repo=gcm&amp;type=star&amp;count=true&amp;size=large"
            frameBorder={0}
            scrolling={0}
            width={160}
            height={30}
            title="GitHub Stars"
          />
        </span>
      </div>
    </header>
  );
}

export default function Home() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <Layout
      title={`${siteConfig.title}`}
      description="GPU Cluster Monitoring (GCM): Large-Scale AI Research Cluster Monitoring. ">
      <HomepageHeader />
      <main>
        <HomepageFeatures />
      </main>
    </Layout>
  );
}
