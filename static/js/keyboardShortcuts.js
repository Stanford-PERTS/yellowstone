/* 
Keyboard shortcuts

Are rather easy to build with the mousetrap library [1]. 
Mousetrap and this file are included in base and so
these shortcuts are global.

Perts short cuts should begin with 'p p' by convention.

[1]: http://craig.is/killing/mice
*/

if (normalUserType === 'god' || normalUserType === 'researcher') {
    // Admin tools
    // Hide or show administrative controls with a keyboard shortcut
    Mousetrap.bind('p p a', function () {
        'use strict';
        $('.admin-control').toggle("fast");
        // Without this timeout, keystrokes from the "ppa" shortcut were
        // ending up getting entered in the search field.
        setTimeout(function () { $('#search').focus(); }, 1);
    });

    // hide
    Mousetrap.bind('esc', function () {
        'use strict';
        $('.admin-control').hide("fast");
    });

    // Show extra information, like entity ids, on dashboard.
    Mousetrap.bind('p p i', function () {
        'use strict';
        $('.id-display').toggle("fast");
    });
}
