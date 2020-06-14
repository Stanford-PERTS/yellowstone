// Javascript for student sign in.

PertsApp.controller('IdentifyController', [
    '$scope', '$pertsAjax', '$timeout', '$window',
    function ($scope, $pertsAjax, $timeout, $window) {
        'use strict';

        var x;
        // This phase var will be used for ng-show in place of the partialMatches
        // 'phase 1' corresponds to the initial login div.
        // 'phase 2' corresponds to the partial matches div.
        // 'phase 3' corresponds to the new user div.
        $scope.phase = 1;
        $scope.identificationType = 'default';
        $scope.doubleCheckNewUser = false;

        $scope.alerts = {};

        // Cohort/session code must be two words and then a digit, separated by
        // single spaces.
        $scope.codeRegex = /^(\S+ \S+) (\d)$/;

        $scope.middleInitialRegex = /^[A-Za-z]$/;

        $scope.days = util.rangeInclusive(1, 31);

        $scope.months = ['January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'];

        $scope.years = util.rangeInclusive(1940, 2010);

        // These two are used in ng-show directives
        $scope.classroomList = [];
        $scope.partialMatches = [];  // will be an array

        $scope.identifyData = {};

        $scope.nonStudentLogIn = window.nonStudentLogIn;
        $scope.studentAlreadyLoggedIn = window.studentAlreadyLoggedIn;

        $scope.$watch('birth', function (value) {
            var b = $scope.birth;
            if (b && b.year && b.month && b.day) {
                // Months are indexed from zero above, so this is correct.
                var d = new Date(b.year, b.month, b.day);
                $scope.identifyData.birth_date = d.toDateString('local');
            }
        }, true);

        // 10 seconds after the user starts typing the code, if they haven't typed
        // something valid yet, show them a help message.
        $scope.$watch('identifyForm.code.$pristine', function (pristine) {
            if (pristine) { return; }

            $timeout(function () {
                if ($scope.identifyForm.code.$invalid) {
                    $scope.alerts.codeHint = true;
                }
            }, 10 * 1000);
        });

        $scope.getCohort = function (code) {
            $scope.alerts = {};

            // Break up the code (e.g. 'trout viper 2') into the cohort part
            // ('trout viper') and the session number ('2').
            var parts = $scope.codeRegex.exec(code.toLowerCase());
            if (parts === null) {
                // This shouldn't happen b/c angular is validating against the
                // regex before the user is allowed to get this far.
                throw new Error("Invalid code in identify: " + code);
            }
            var cohortCode = parts[1];
            $scope.sessionOrdinal = parts[2];

            var url = '/api/public_cohort_details?code=' +
                encodeURIComponent(cohortCode);

            $pertsAjax({url: url}).then(function (response) {
                if (response.length === 0) {
                    $scope.alerts.badCodeError = true;
                } else {
                    $scope.cohort = response[0];
                    $scope.getClasses($scope.cohort);
                }
            });
        };

        $scope.getClasses = function (cohort) {
            var url = '/api/see/classroom?assc_cohort_list=' + cohort.id;
            $pertsAjax({url: url}).then(function (response) {
                if (response.length === 0) {
                    $window.onerror(
                        "Cohort has no classrooms: " + cohort.name + ".");
                } else {
                    $scope.classroomList = response;
                    if ($scope.cohort.identification_type === 'dissemination') {
                        // Special rule for dissemination-style cohorts:
                        // there's only one classroom, so pre-select it
                        // (there's no UI for the classroom in this case
                        // anyway).
                        $scope.identifyData.classroom = $scope.classroomList[0].id;
                    }
                }
            });
        };

        $scope.phaseValid = function (phaseNum) {
            if (!$scope.cohort) { return false; }

            var form, buttonClicked, middleInitialValid;

            // The function is used to validate forms in both phase 1 and 3.
            if (phaseNum === 1) {
                form = $scope.identifyForm;
                buttonClicked = $scope.identifyButtonClicked;
            } else if (phaseNum === 3) {
                form = $scope.confirmNewUserForm;
                buttonClicked = $scope.confirmNewUserButtonClicked;
            }

            if (form.middle_initial) {
                // Middle initial must be valid and non-blank OR user must
                // affirm that they have none.
                middleInitialValid = (
                    $scope.hasNoMiddleName ||
                    (
                        !form.middle_initial.$invalid &&
                        $scope.identifyData.middle_initial
                    )
                );

                return middleInitialValid && !form.$invalid && !buttonClicked;
            } else {
                return !form.$invalid && !buttonClicked;
            }
        };

        $scope.identify = function () {
            $scope.identifyButtonClicked = true;

            // The user types their whole alias into one box. Split it up into
            // first name and last name, which the server expects.
            if ($scope.cohort.identification_type === 'alias') {
                var aliases = $scope.alias.split(' ');
                $scope.identifyData.first_name = aliases[0] || '';
                $scope.identifyData.last_name = aliases[1] || '';
            } else if ($scope.cohort.identification_type === 'dissemination') {
                if (parseInt($scope.sessionOrdinal, 10) === 1) {
                    // For dissemination-style identification, we don't expect
                    // any rosters to be entered before hand, so session 1
                    // students should skip the double-check phase.
                    $scope.identifyData.force_create = true;
                }
            }

            $pertsAjax({
                url: '/api/identify',
                params: $scope.identifyData
            }).then(function (response) {
                if (response === 'logout_required') {
                    // Somehow the user made this call without being logged out
                    // first. Force them to log out.
                    $window.location.href = '/logout?redirect=/go';
                } else if (response.exact_match) {
                    $scope.redirectToActivities($scope.identifyData.classroom);
                } else if (response.new_user) {
                    // set double check variable to true
                    $scope.doubleCheckNewUser = true;
                    // set phase to 3
                    $scope.phase = 3;
                    $('body,html').animate({scrollTop:0},0);
                } else if ($scope.cohort.identification_type === 'alias') {
                    // When using aliases, don't bother with partial matches.
                    // Just tell the user they typed their name wrong.
                    $scope.alerts.badNameError = true;
                    // Avoid data binding in alert message.
                    $scope.alerts.badNameValue = $scope.identifyData.first_name +
                        " " + $scope.identifyData.last_name;
                    // Allow student to click the button again.
                    $scope.identifyButtonClicked = false;
                    $('body,html').animate({scrollTop:0},0);
                } else {
                    // no exact match found, so show the user the partials
                    $scope.partialMatches = response.partial_matches;
                    $scope.partialMatches.push({id: 'none', last_name: '', first_name: 'None of the above'});
                    // set phase to 2
                    $scope.phase = 2;
                    $('body,html').animate({scrollTop:0},0);
                }
            });
        };

        $scope.choosePartialMatch = function () {
            if ($scope.partialMatchChoice === 'none') {
                // set the double check var to true
                $scope.doubleCheckNewUser = true;
                // set the phase to 3
                $scope.phase = 3;
                $('body,html').animate({scrollTop:0},0);
                // This is the way it was done in Pegasus:
                // $scope.identifyData.force_create = 'true';
                // $scope.identify();
            } else {
                var classroomId = $scope.identifyData.classroom;
                $pertsAjax({
                    url: '/api/identify',
                    params: {
                        user: $scope.partialMatchChoice,
                        classroom: classroomId
                    }
                }).then($scope.redirectToActivities.partial(classroomId));
            }
        };

        $scope.confirmNewUser = function () {
            $scope.confirmNewUserButtonClicked = true;
            $scope.identifyData.force_create = true;
            $scope.identify();
        };

        $scope.redirectToActivities = function (classroomId) {
            var url = '?cohort=' + $scope.cohort.id + '&classroom=' +
                      classroomId + '&session_ordinal=' + $scope.sessionOrdinal +
                      '&page_action=go_to_program';
            window.location.href = url;
        };
    }
]);
