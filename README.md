Yellowstone
=======

The PERTS platform and homepage: [perts.net](https://www.perts.net).

## Bootstrapping

Just cloned? Follow these steps.

You should already have the Google Cloud SDK and NodeJS installed. If you don't:

1. Install the [google cloud sdk](https://cloud.google.com/sdk/). Note that modern Macs are 64 bit. After installing the sdk, also install the python app engine components (see [PERTS docs on install details](https://docs.google.com/document/d/184dsSF-esWgJ-TS_da3--UkFNb1oIur-r99X-7Xmhfg/edit#heading=h.s4e9sakq3rr5)). Run `gcloud components update` if you already have the sdk installed.
2. Install the newest LTS version of [nodeJS](https://nodejs.org/en/) (last documented at 8.11.1).

With that system-wide software installed, set up Yellowstone:

1. In a terminal, `cd` into your yellowstone directory, e.g. `cd yellowstone`.
2. Run `npm install`.
3. Run `npm start`.
4. Open a new terminal (⌘T or ⌘N).
5. Run `npm run server`.
6. Open `localhost:9080` in your browser.

## Using SASS

This application uses SASS (`*.scss`) which compiles to CSS stylesheets.  SASS allows for nested styles, cross-browser mixins, variables, and much more.

To make any CSS changes, make sure you've completed the steps in [Bootstrapping](#bootstrapping). Then edit the files in `/sass`. They will automatically be compiled when you save the edited file. Then refresh your browser to see changes.

#### Local Server

```
$ npm start
```

Watches `.scss` files to recompile corresponding `.css` so you can see changes locally as you update the files.

#### Production

```
$ npm run sass:build
```

Builds a minified production stylesheet
