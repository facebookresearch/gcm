// @ts-check
// `@type` JSDoc annotations allow editor autocompletion and type checking
// (when paired with `@ts-check`).
// There are various equivalent ways to declare your Docusaurus config.
// See: https://docusaurus.io/docs/api/docusaurus-config

import {themes as prismThemes} from 'prism-react-renderer';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'Meta GPU Cluster Monitoring (GCM)',
  tagline: 'GCM: Large-Scale AI Research Cluster Monitoring.',
  // favicon: '/img/gcm_white.svg',

  headTags: [
    {
      tagName: "link",
      attributes: {
        rel: "icon",
        href: "/img/gcm_black.svg",
        type: "image/svg+xml",
        sizes: "32x32",
        media: "(prefers-color-scheme: light)",
      },
    },
    {
      tagName: "link",
      attributes: {
        rel: "icon",
        href: "/img/gcm_white.svg",
        type: "image/svg+xml",
        sizes: "32x32",
        media: "(prefers-color-scheme: dark)",
      },
    },
  ],

  // Future flags, see https://docusaurus.io/docs/api/docusaurus-config#future
  future: {
    v4: true, // Improve compatibility with the upcoming Docusaurus v4
  },

  // Set the production url of your site here
  url: 'https://facebookresearch.github.io/',
  // Set the /<baseUrl>/ pathname under which your site is served
  // For GitHub pages deployment, it is often '/<projectName>/'
  baseUrl: '/gcm/',
  trailingSlash: true,

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: 'facebookresearch', // Usually your GitHub org/user name.
  projectName: 'gcm', // Usually your repo name.

  onBrokenLinks: 'throw',

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          sidebarPath: './sidebars.js',
          // Please change this to your repo.
          // Remove this to remove the "edit this page" links.
          editUrl:
            'https://github.com/facebookresearch/gcm/tree/main/website/',
        },
        theme: {
          customCss: './src/css/custom.css',
        },
        gtag: {
          trackingID: 'G-1NJ0H4237Y',
          anonymizeIP: true,
        },
      }),
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({

      // Replace with your project's social card
      colorMode: {
        respectPrefersColorScheme: true,
      },
      navbar: {
        title: 'GCM',
        logo: {
          alt: 'GCM Logo',
          src: '/img/gcm_black.svg',
          srcDark: '/img/gcm_white.svg',
        },
        items: [
          {
            type: 'docSidebar',
            sidebarId: 'tutorialSidebar',
            position: 'left',
            label: 'Docs',
          },
          // {
          //   to: '/blog',
          //   position: 'left',
          //   label: 'Blog',
          // },
          // TODO: blog
          // {
          //   href: 'https://github.com/facebookresearch/gcm',
          //   position: 'left',
          //   label: 'Meta Blog Post',
          // },
          {
            href: 'https://github.com/facebookresearch/gcm',
            label: 'GitHub',
            position: 'right',
          },
          {
            href: 'https://pypi.org/project/gpucm',
            label: 'Pypi',
            position: 'right',
          },
          {
            href: 'https://github.com/facebookresearch/gcm/discussions',
            label: 'Discussions',
            position: 'right',
          },
        ],
      },
      footer: {
        style: 'dark',
        links: [
          {
            title: 'Links',
            items: [
              {
                label: 'Docs',
                to: '/docs/getting_started',
              },
              // {
              //   label: 'Blog',
              //   to: '/blog',
              // },
              // TODO: blog
              // {
              //   label: 'Meta Blog Post',
              //   to: '/blog',
              // },
              {
                label: 'Github',
                href: 'https://github.com/facebookresearch/gcm',
              },
              {
                label: 'Pypi',
                href: 'https://pypi.org/project/gpucm/',
              },
              {
                label: 'Discussions',
                href: 'https://github.com/facebookresearch/gcm/discussions',
              },
            ],
          },
          {
            title: 'Legal',
            items: [
              {
                label: 'Privacy',
                href: 'https://opensource.fb.com/legal/privacy/',
                target: '_blank',
                rel: 'noreferrer noopener',
              },
              {
                label: 'Terms',
                href: 'https://opensource.fb.com/legal/terms/',
                target: '_blank',
                rel: 'noreferrer noopener',
              },
              {
                label: 'Cookies',
                href: 'https://opensource.fb.com/legal/cookie-policy/',
                target: '_blank',
                rel: 'noreferrer noopener',
              },
            ],
          },
        ],
        logo: {
          alt: 'Meta Open Source Logo',
          src: '/img/meta_opensource_logo_negative.svg',
          href: 'https://opensource.fb.com',
        },
        copyright: `Copyright © ${new Date().getFullYear()} Meta Platforms, Inc. Built with Docusaurus.`,
      },
      prism: {
        theme: prismThemes.github,
        darkTheme: prismThemes.dracula,
      },
      algolia: {
        appId: '7UME3HJQQL',
        apiKey: '22e43927eed85234ea84061f1292dab9',
        indexName: 'gcm'
      }
    }),

  plugins: [
    // Your plugin goes HERE as a function
    function(context, options) {
      return {
        name: 'custom-webpack-config',
        configureWebpack(config, isServer, utils) {
          return {
            resolve: {
              symlinks: true,
            },
          };
        },
      };
    },
  ],
};

export default config;
