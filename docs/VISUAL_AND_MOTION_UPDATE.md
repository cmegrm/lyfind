# Visual and motion update

The October 29, 2026 update expands the LPU Cavite inspired theme into a consistent interface with the exact supplied university crest, burgundy navigation, champagne accents, warm ivory backgrounds, and a unified set of locally authored SVG icons. It uses no external fonts, image services, or animation libraries.

## Interface improvements

- A layered sign-in scene with floating report and return cards, orbit details, an editorial headline, and clear account choices.
- A sliding sign-in tab indicator and keyboard support for arrow keys, Home, and End.
- A burgundy workspace sidebar, clearer cards and tables, genuine database totals, and role-specific quick actions.
- Staged page entrances, number transitions when totals change, hover and press feedback, button ripples, animated dialogs, and a request progress line.
- Better form spacing, selected-image previews, loading indicators, clearer success notices, and a distinct local email-code notice.
- Search updates only the inventory results, retaining focus and text selection rather than rebuilding the page.
- A mobile navigation drawer with an overlay, keyboard focus handling, Escape dismissal, and inaccessible closed links.
- Reduced-motion support and paused ambient animations while the page is hidden.

## Verification

JavaScript syntax validation passed. The existing 35 domain, database, authentication, and HTTP tests passed again. Browser review checked the sign-in layout, keyboard tab navigation, staff sign-in, inventory filtering with retained focus, form appearance, dialog dismissal, successful report saving, and mobile drawer behavior. The reviewed desktop and phone layouts had no horizontal page overflow. Browser image-upload verification was not completed because upload permission was declined; a report without its optional image was saved successfully instead.

Browser form testing used a separate preview database. The test report was confirmed absent from the application's existing database. The production data folder is excluded from the downloadable archive.

## Apply the update

For this working copy, refresh the app using **Ctrl+F5**. For a separately extracted installation, replace only its **static** folder with the updated **static** folder, then refresh. Keep the existing **data** folder to retain saved records and uploads. The update requires no database migration.

The identity integrations still use the configuration described in the main setup guide. Visual changes do not configure Microsoft or SMTP services.
