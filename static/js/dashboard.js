// Contains defintions for all the widgets (angular directives) that drive
// the dashboard.


var relationshipListNames = [
    'owned_program_list',
    'assc_program_list',
    'owned_school_list',
    'assc_school_list',
    'owned_cohort_list',
    'assc_cohort_list',
    'owned_classroom_list',
    'assc_classroom_list'
];

// x = 1, y = 5, returns '20%'
// x = 1, y = 0, returns '--'
function getPercentString(x, y, divideByZeroValue) {
    'use strict';
    if (divideByZeroValue === undefined) { divideByZeroValue = '--'; }
    return y > 0 ? Math.round(x / y * 100) + '%' : divideByZeroValue;
}

function tableCellToValue(td) {
    'use strict';
    // We want to output a string in every case such that it is both
    // sortable and searchable.
    var value;

    var selectResult = $('select', td);
    var datepickrResult = $('input[class*="datepickr"]', td);
    var textInputResult = $('input[type="text"]', td);

    // Does this column contain a <select>? If so, sort on its displayed text,
    // not the text of all its contents/children, and not its values.
    if (selectResult.length > 0) {
        value = $('option:selected', selectResult).text();
    }
    // Does this column contain a datepickr calendar? If so, sort on
    // its value.
    else if (datepickrResult.length > 0) {
        var date = datepickrResult.get(0)._currentValue;
        // ISO strings are good because they are correctly sortabe as-is. Also
        // allow for dates not being defined yet.
        value = date ? date.toISOString() : '';
    }
    // Does this column contain a text box? Sort on its value.
    else if (textInputResult.length > 0) {
        value = textInputResult.val();
    }
    // Otherwise just look at the text in the <td>
    else {
        value = $(td).text();
    }
    return value.toLowerCase();
}

function sortByFactory(scope, tableNode, tbodyOrTr) {
    'use strict';
    return function (col) {
        // Only provide sorting on columns marked sortable.
        if (!scope.columns[col].sortable) { return; }

        var rowQuery, parentQuery;
        if (tbodyOrTr === 'tr') {
            // This means treat <tr>s as rows, for tables with one <tbody>
            rowQuery = $.partial('tbody tr', tableNode);
            parentQuery = $.partial('tbody', tableNode);
        } else if (tbodyOrTr === 'tbody') {
            // The other value, 'tbody', means treat <tbody>s as rows, for tables
            // with many <tbody>s.
            rowQuery = $.partial('tbody', tableNode);
            parentQuery = $.partial(tableNode);
        }
        if (scope.reverseSort === undefined) {
            scope.reverseSort = false;
        }
        if (scope.sortedColumn === col) {
            scope.reverseSort = !scope.reverseSort;
        }
        var rows = rowQuery().get();

        // The stability of javascript sorting is implementation-depedendent.
        // http://blog.8thlight.com/will-warner/2013/03/26/stable-sorting-in-ruby.html
        // http://stackoverflow.com/questions/3026281/array-sort-sorting-stability-in-different-browsers
        // We can ensure stable sorting by sorting otherwise-equal elements
        // by their original position in the list. So determine those original
        // positions here.
        forEach(rows, function (r, position) {
            r._originalPosition = position;
        });

        rows.sort(function (a, b) {
            // Include the :visible selector b/c sometimes I have tables doing
            // tricky games where they have cells that are hidden in certain
            // modes and visible in other modes. We want to pretend like the
            // invisible cells aren't there otherwise counting columns from
            // the left via col will be wrong.
            var tdA = $(a).find('td:visible').eq(col);
            var tdB = $(b).find('td:visible').eq(col);
            var A = tableCellToValue(tdA);
            var B = tableCellToValue(tdB);

            // Are A and B numeric? If so, compare them as numbers, b/c
            // '10' > '100', but 100 > 10.
            if (util.isStringNumeric(A, 'strict') && util.isStringNumeric(B, 'strict')) {
                A = Number(A);
                B = Number(B);
            }

            var direction = scope.reverseSort ? -1 : 1;
            if (A < B) { return direction * -1; }
            if (A > B) { return direction; }

            // These elements appear equal. To ensure stable sorting, sort by
            // their original position before the sort started.
            return (a._originalPosition - b._originalPosition) * direction;
        });
        // var x = 0;
        forEach(rows, function (row) {
            parentQuery().append(row);
            // x++;
        });
        scope.sortedColumn = col;
    };
}

function watchFilter(scope, element) {
    'use strict';

    // Whenever the user focuses on the search box to begin filtering the
    // table, update the string representation of the row. We'll search on
    // this string.
    scope.$on('/dashboardTable/filterFocus', function (event) {
        var valueArr = [];
        $('td', element).each(function (index, td) {
            valueArr.push(tableCellToValue(td));
        });
        scope.stringRepresentation = valueArr.join(' ');
    });

    scope.$watch('filterText', function (filterText) {
        if (typeof filterText !== 'string') { return; }

        filterText = filterText.toLowerCase();

        if (
            ['', undefined, null].contains(filterText) ||
            scope.stringRepresentation.contains(filterText)
        ) {
            element.removeClass('ng-hide');
        } else {
            element.addClass('ng-hide');
        }
    });
}

function sortIconClassFactory($scope) {
    'use strict';
    return function (col) {
        // Only provide sorting icons on columns marked sortable.
        if (!$scope.columns[col].sortable) { return; }

        var out = ['clickable_cursor'];
        if ($scope.sortedColumn === col) {
            if ($scope.reverseSort) {
                out.push('reverse-sort');
            } else {
                out.push('normal-sort');
            }
        }
        return out.join(' ');
    };
}


function getAllReferencedIds(user, $window) {
    'use strict';
    var entityIds = [];
    forEach($window.relationshipListNames, function (listName) {
        entityIds = entityIds.concat(user[listName]);
    });
    // eliminate duplicates and remove falsy values
    return util.arrayUnique(entityIds).filter(function (v) {
        return Boolean(v);
    });
}

function getInterpretedStatus(activity, forcedStatus) {
    'use strict';
    if (!activity) { return; }
    // @todo:
    // If multi-day activity:
    // interpreted status = status
    var today = new Date();
    var scheduled_date;
    if (!activity.scheduled_date) {
        scheduled_date = false;
    } else {
        scheduled_date = Date.createFromString(activity.scheduled_date, 'local');
    }
    // Default to the activity's status, unless it was overwritten by the
    // optional forcedStatus argument.
    var status = forcedStatus ? forcedStatus : activity.status;
    var interpretedStatus;
    if (status === 'completed' || status === 'aborted') {
        interpretedStatus = activity.status;
    } else if (!scheduled_date) {
        interpretedStatus = 'unscheduled';
    } else if (Date.dayDifference(today, scheduled_date) > 3) {
        interpretedStatus = 'behind';
    } else {
        interpretedStatus = 'scheduled';
    }
    return interpretedStatus;
}

function DashboardController($scope, $routeParams, $emptyPromise, $location, $window, $getStore) {
    'use strict';
    $scope.$root.userType = $window.userType;
    $scope.$root.userId = $window.userId;

    $scope.$root.programOutlines = [];
    $scope.breadcrumbs = [];

    if ($routeParams.level && $routeParams.entityId && $routeParams.page) {
        $scope.$root.level = $routeParams.level;
        $scope.$root.entityId = $routeParams.entityId;
        $scope.$root.page = $routeParams.page;
    } else {  // The hash isn't right, or the user has just arrived and has none
        // Signals certain widgets to redirect to more specific realms if they
        // are only showing one thing.
        $scope.$root.redirecting = true;
        $location.path('/programs/all/program_progress');
        return;
    }

    $scope.$root.levelLables = {
        'programs': 'Global level',
        'program': 'Study level',
        'cohort': 'School level',
        'classroom': 'Classroom level'
    };

    $scope.$root.programs = {id: 'all', name: 'Dashboard Home'};

    if (['programs'].contains($routeParams.level)) {
        // There's no entity to load, just provide a stub that fills in
        // appropriate text to display
        $scope.$root.user = $getStore.get($scope.$root.userId);
        $scope.$root.currentEntity = $scope.$root[$routeParams.level];
    } else {
        // There is an entity providing context for this view; load it and its
        // parents
        $getStore.load([$scope.$root.userId, $scope.$root.entityId]);
        $scope.$root.user = $getStore.get($scope.$root.userId);
        $scope.$root.currentEntity = $getStore.get($scope.$root.entityId);
    }
    var programId, schoolId, cohortId;
    var contextLoaded;  // a promise to attach breadcrumb definition to
    $scope.$watch('currentEntity', function (value) {
        if (value.name !== undefined) {
            // then the current entity has been loaded, and we can look at it...
            if ($scope.$root.level === 'program') {
                $scope.$root.program = $scope.$root.currentEntity;
                if ($scope.$root.page === 'cohort_progress') {
                    $scope.$root.programList = [$scope.$root.program];
                }
            } else if ($scope.$root.level === 'cohort') {
                $scope.$root.cohort = $scope.$root.currentEntity;
                programId = $scope.$root.cohort.assc_program_list[0];
                schoolId = $scope.$root.cohort.assc_school_list[0];
                contextLoaded = $getStore.load([programId, schoolId]);
                $scope.$root.program = $getStore.get(programId);
                $scope.$root.school = $getStore.get(schoolId);
            } else if ($scope.$root.level === 'classroom') {
                $scope.$root.classroom = $scope.$root.currentEntity;
                // schoolId = $scope.classroom.assc_school_list[0];
                programId = $scope.classroom.assc_program_list[0];
                cohortId = $scope.classroom.assc_cohort_list[0];
                // contextLoaded = $getStore.load([schoolId, programId, cohortId]);
                contextLoaded = $getStore.load([programId, cohortId]);
                $scope.$root.cohort = $getStore.get(cohortId);
                $scope.$root.program = $getStore.get(programId);
                $scope.$root.school = $getStore.get(schoolId);
            }
            if (contextLoaded === undefined) {
                contextLoaded = $emptyPromise();
            }
            contextLoaded.then(function () {
                $scope.generateBreadcrumbs();
            });
        }
    }, true);  // true here means watch object value, not object reference
    // (the entity store is specifically designed NOT to change object
    // references)

    // Configure navigation tabs
    var tabConfig = {
        programs: [
            {id: 'program_progress', name: 'Tracking'}
        ],
        program: [
            {id: 'cohort_progress', name: 'Tracking'},
            {id: 'educators', name: 'All Coordinators'}
        ],
        cohort: [
            {id: 'classroom_progress', name: 'Schedule'},
            {id: 'roster', name: 'School Roster'},
            {id: 'makeups', name: 'School Make-Ups'},
            {id: 'educators', name: 'School Coordinators'},
            {id: 'detail', name: 'Edit School Details'}
        ],
        classroom: [
            {id: 'roster', name: 'Classroom Roster'},
            {id: 'makeups', name: 'Classroom Make-Ups'},
            {id: 'detail', name: 'Edit Classroom Details'}
        ]
    };

    $scope.tabs = tabConfig[$scope.$root.level];
    $scope.tabClass = function (tabId) {
        return tabId === $scope.$root.page ? 'active' : '';
    };

    $scope.generateBreadcrumbs = function () {
        var parents;
        /*jshint ignore:start*/
        switch ($scope.$root.level) {
        case 'schools':   parents = [];  break;
        case 'educators': parents = [];  break;
        case 'programs':  parents = [];  break;
        case 'program':   parents = [];
                          if ($scope.$root.userType === 'god') {
                              parents.unshift('programs');
                          }
                          break;
        case 'cohort':    parents = ['program'];
                          if ($scope.$root.userType === 'god') {
                              parents.unshift('programs');
                          }
                          break;
        case 'classroom': parents = ['program', 'cohort'];
                          if ($scope.$root.userType === 'god') {
                              parents.unshift('programs');
                          }
                          break;
        }
        /*jshint ignore:end*/
        var b = [];
        if (parents === undefined) {
            return {};
        } else if (parents.length > 0) {
            b = forEach(parents, function (lvl) {
                if ($scope.$root[lvl]) {
                    return {
                        link: '/' + lvl +
                            '/' + $scope[lvl].id +
                            '/' + tabConfig[lvl][0].id,
                        name: $scope[lvl].name
                    };
                }
            });
        }
        b.push({name: $scope.$root.currentEntity.name});
        $scope.breadcrumbs = b;
    };

    // The detail page changes template based on the level
    $scope.detailTemplateUrl = '/static/dashboard_pages/' + $scope.$root.level + '_detail.html';

    // b/c our current version of angular doesn't support dynamic templates,
    // this is a little hack to change up the template based on the route.
    // @todo: fix this when >= 1.1.2 becomes stable.
    $scope.templateUrl = '/static/dashboard_pages/' + $scope.$root.page + '.html';
}

//  *************************  //
//  ******** WIDGETS ********  //
//  *************************  //

PertsApp.directive('programAdmins', function () {
    'use strict';
    return {
        scope: {
            programId: '@programId'
        },
        controller: function ($scope, $seeStore, $getStore, $pertsAjax) {
            $scope.$watch('programId', function (value) {
                if (value) {
                    $scope.program = $getStore.get(value);
                    $scope.getAssociatedUsers();
                }
            });
            $scope.getAssociatedUsers = function () {
                // to display admins, we need to see all associated users
                $pertsAjax({
                    url: '/api/see/user',
                    params: {
                        user_type: 'school_admin',
                        assc_program_list: $scope.program.id
                    }
                }).then(function (response) {
                    $scope.adminList = forEach(response, function (admin) {
                        return $seeStore.set(admin);
                    });
                });
            };
        },
        templateUrl: '/static/dashboard_widgets/program_admins.html'
    };
});

PertsApp.directive('programProgressList', function () {
    'use strict';
    return {
        scope: {},
        controller: function ($scope, $getStore, $pertsAjax, $location) {
            // We'll need all the user's programs
            $pertsAjax({url: '/api/get/program'}).then(function (response) {
                $scope.programList = $getStore.setList(response);
                var programIds = forEach($scope.programList, function (program) {
                    return program.id;
                });

                if ($scope.$root.redirecting) {
                    if ($scope.programList.length === 1) {
                        $location.path('/program/' + $scope.programList[0].id +
                                       '/cohort_progress');
                        return;
                    } else {
                        // this is the right place to be; stop redirection
                        $scope.$root.redirecting = false;
                    }
                }

                // ... and all the cohorts associated with those programs.
                $pertsAjax({
                    url: '/api/get/cohort',
                    params: {assc_program_list_json: programIds}
                }).then(function (response) {
                    $scope.cohortList = $getStore.setList(response);
                    // Index the cohorts by program so they can be passed to
                    // the correct child.
                    $scope.cohortIndex = {};
                    forEach($scope.cohortList, function (cohort) {
                        var programId = cohort.assc_program_list[0];
                        util.initProp($scope.cohortIndex, programId, []);
                        $scope.cohortIndex[programId].push(cohort.id);
                    });
                });
            });
        },
        templateUrl: '/static/dashboard_widgets/program_progress_list.html'
    };
});

PertsApp.directive('programProgress', function () {
    'use strict';
    var scope = {
        programId: '@programId',
        cohortIds: '@cohortIds'
    };
    var controller = function ($scope, $getStore, $pertsAjax, $window) {
        $scope.$watch('programId', function (value) {
            $scope.program = $getStore.get(value);
            $scope.outline = $window.programInfo[$scope.program.id];
        });
        $scope.$watch('cohortIds', function (cohortIds) {
            if (cohortIds) {
                $scope.buildRows($scope.outline.student_outline);
            }
        });
        $scope.buildRows = function (studentOutline) {
            $scope.rows = [];
            forEach(studentOutline, function (module) {
                if (module.type === 'activity') {
                    $scope.rows.push({
                        cohortIds: $scope.cohortIds,
                        activityOrdinal: module.activity_ordinal,
                        name: module.name
                    });
                }
            });
        };
        $scope.columns = [
            {name: "School", tooltip: "School name",
             colClass: 'name', sortable: true}, // really a cohort name
            {name: "#", tooltip: "Session number",
             colClass: 'session', sortable: true},
            // <classroom session status>
            {name: "Unschd", tooltip: "Unscheduled: number of classrooms who haven't set a date for their session.",
             colClass: 'unscheduled', sortable: true},
            {name: "Bhnd", tooltip: "Behind: number of classrooms behind schedule.",
             colClass: 'behind', sortable: true},
            {name: "Schd/ Compl", tooltip: "Scheduled/Completed: Number of classrooms on track.",
             colClass: 'scheduled_completed', sortable: true},
            {name: "Total", tooltip: "Total number of classrooms.",
             colClass: 'total', sortable: true},
            // </classroom session status>
            // <certified study eligible students>
            {name: "Total", colClass: 'study_eligible', sortable: true,
             tooltip: "All certified, study eligible students."},
            {name: "Cmpl", colClass: 'completed', sortable: true,
             tooltip: "Complete: students who have completed the session, as a percent of study eligible students."},
            {name: "Makeup Inelg", colClass: 'makeup_ineligible', sortable: true,
             tooltip: "Makeup Ineligible: students who may NOT participate in a make up session."},
            {name: "Makeup Elg", colClass: 'makeup_eligible', sortable: true,
             tooltip: "Makeup Eligible: students who MAY participate in a make up session."},
            {name: "Not Coded", colClass: 'uncoded', sortable: true,
             tooltip: "Students who should either 1) complete the session " +
                      "or 2) be given a code explaining why they haven't."}
            // </certified study eligible students>
        ];

        // Put in a kinda-crappy replacement of an input placeholder for
        // browsers which don't support placeholders.
        // The timeout lets us escape angular's digest loop, so setting
        // the value of the input *won't* be recognized as an actual
        // attempt to search, which is what we want.
        if (!util.weHas.placeholder()) {
            setTimeout(function () {
                $('.dashboard-table-controls [placeholder]').val('Search...');
            }, 1);
        }
    };
    return {
        scope: scope,
        controller: controller,
        link: function (scope, element, attrs) {
            // running sortBy sets scope.reverseSort and scope.sortedColumn
            scope.sortBy = sortByFactory(scope, element, 'tr');
            scope.sortIconClass = sortIconClassFactory(scope);
        },
        templateUrl: '/static/dashboard_widgets/program_progress.html'
    };
});

PertsApp.directive('cohortEntry', function () {
    'use strict';
    return {
        scope: {
            cohortId: '@cohortId'
        },
        controller: function ($scope, $getStore, $window) {
            $scope.$watch('cohortId', function (value) {
                $scope.cohort = $getStore.get(value);
                // @todo: there's a lot of things we could try to load if we
                // wanted, because there's a lot of widgets nested under here.
            });
            $scope.userType = $window.userType;
            $scope.show = function () {
                return $scope.$root.level === 'cohort' ||
                    $scope.$root.level === 'classroom';
            };
        },
        templateUrl: '/static/dashboard_widgets/cohort_entry.html'
    };
});

PertsApp.directive('cohortBasics', function () {
    'use strict';
    return {
        scope: {
            cohortId: '@cohortId'
        },
        controller: function ($scope, $getStore, $pertsAjax, $location) {
            $scope.$watch('cohortId', function (value) {
                $scope.cohort = $getStore.get(value);
            });
            $scope.$watch('cohort.assc_school_list', function () {
                if (!$scope.cohort.assc_school_list) { return; }
                $scope.school = $getStore.get($scope.cohort.assc_school_list[0]);
            });
            $scope.show = function () {
                return $scope.$root.level === 'program' ||
                    $scope.$root.level === 'cohort' ||
                    $scope.$root.level === 'classroom';
            };
            $scope.deleteCohort = function (cohort) {
                if (confirm("Are you sure you want to delete " + cohort.name + "?")) {
                    var url = '/api/delete/cohort/' + cohort.id;
                    $pertsAjax({url: url}).then(function () {
                        $location.path('/');
                    });
                }
            };
        },
        templateUrl: '/static/dashboard_widgets/cohort_basics.html'
    };
});

PertsApp.directive('cohortAdmins', function () {
    'use strict';
    return {
        scope: {
            cohortId: '@cohortId'
        },
        controller: function ($scope, $getStore, $pertsAjax) {
            $scope.$watch('cohortId', function (value) {
                if (value) {
                    $scope.cohort = $getStore.get(value);
                    $scope.getAssociatedUsers();
                }
            });
            $scope.getAssociatedUsers = function () {
                // to display admins, we need to see all associated users
                $pertsAjax({
                    url: '/api/get/user',
                    params: {
                        user_type: 'school_admin',
                        owned_cohort_list: $scope.cohort.id
                    }
                }).then(function (response) {
                    $scope.adminList = forEach(response, function (admin) {
                        return $getStore.set(admin);
                    });
                });
            };
            $scope.noAdmins = function () {
                // to display admins, we need to see all associated users
                if ($scope.adminList) {
                    return $scope.adminList.length === 0;
                }
            };
        },
        templateUrl: '/static/dashboard_widgets/cohort_admins.html'
    };
});

// Displays statistics broken down by cohort for all the cohorts in a program.
// Calls aggregateCohortProgress for each item in the list.
PertsApp.directive('cohortProgressList', function () {
    'use strict';
    var controller = function ($scope, $getStore, $pertsAjax, $location, $window) {
        $scope.identificationType = 'default';
        // get all the cohorts visible to the user in this program
        $pertsAjax({
            url: '/api/get/cohort',
            params: {
                assc_program_list: $scope.$root.currentEntity.id,
                order: 'name'
            }
        }).then(function (response) {
            $scope.cohortList = $getStore.setList(response);

            // Figure out if we should automatically redirect elsewhere
            // because the user doesn't have any choices at this level.
            if ($scope.$root.redirecting && $scope.$root.level === 'program') {
                if ($scope.cohortList.length === 1) {
                    $location.path('/cohort/' + $scope.cohortList[0].id +
                                   '/classroom_progress');
                    return;
                } else {
                    // this is the right place to be; stop redirection
                    $scope.$root.redirecting = false;
                }
            }

            // If we're not redirecting, use the program outline to figure
            // out how to organize the cohorts' aggregated data by
            // activity.
            $scope.buildRows();
        });

        // Put in a kinda-crappy replacement of an input placeholder for
        // browsers which don't support placeholders.
        // The timeout lets us escape angular's digest loop, so setting
        // the value of the input *won't* be recognized as an actual
        // attempt to search, which is what we want.
        if (!util.weHas.placeholder()) {
            setTimeout(function () {
                $('.dashboard-table-controls [placeholder]').val('Search...');
            }, 1);
        }

        $scope.buildRows = function () {
            var studentOutline = $window.programInfo[$scope.$root.program.id].student_outline;
            $scope.rows = [];
            $scope.sessions = [];
            forEach($scope.cohortList, function (cohort) {
                forEach(studentOutline, function (module) {
                    if (module.type === 'activity') {
                        $scope.rows.push({
                            cohortIds: [cohort.id],
                            activityOrdinal: module.activity_ordinal,
                            name: module.name
                        });
                        if (!$scope.sessions.contains(module)) {
                            $scope.sessions.push(module);
                        }
                    }
                });
            });
        };

        $scope.createSchool = function () {
            return $pertsAjax({
                url: '/api/put/school',
                params: {name: $scope.schoolName}
            });
        };

        $scope.createCohort = function (school) {
            return $pertsAjax({
                url: '/api/put/cohort',
                params: {
                    name: $scope.schoolName,
                    program: $scope.$root.program.id,
                    school: school.id,
                    identification_type: $scope.identificationType
                }
            });
        };

        $scope.addSchool = function () {
            $scope.createSchool()
            .then($scope.createCohort)
            .then(function (cohort) {
                cohort = $getStore.set(cohort);
                // Add the cohort to the table's list and rebuild it so the
                // new cohort is displayed.
                $scope.cohortList.push(cohort);
                $scope.buildRows();
                // Clear the school name input box.
                $scope.schoolName = '';
            });
        };

        $scope.columns = [
            {name: "School", tooltip: "School name",
             colClass: 'name', sortable: true}, // really a cohort name
            {name: "#", tooltip: "Session number",
             colClass: 'session', sortable: true},
            // <classroom session status>
            {name: "Unschd", tooltip: "Unscheduled: number of classrooms who haven't set a date for their session.",
             colClass: 'unscheduled', sortable: true},
            {name: "Bhnd", tooltip: "Behind: number of classrooms behind schedule.",
             colClass: 'behind', sortable: true},
            {name: "Schd/ Compl", tooltip: "Scheduled/Completed: Number of classrooms on track.",
             colClass: 'scheduled_completed', sortable: true},
            {name: "Total", tooltip: "Total number of classrooms.",
             colClass: 'total', sortable: true},
            // </classroom session status>
            // <certified study eligible students>
            {name: "Total", colClass: 'study_eligible', sortable: true,
             tooltip: "All study eligible students."},
            {name: "Cmpl", colClass: 'completed', sortable: true,
             tooltip: "Complete: students who have completed the session, as a percent of study eligible students."},
            {name: "Makeup Inelg", colClass: 'makeup_ineligible', sortable: true,
             tooltip: "Makeup Ineligible: students who may NOT participate in a make up session."},
            {name: "Makeup Elg", colClass: 'makeup_eligible', sortable: true,
             tooltip: "Makeup Eligible: students who MAY participate in a make up session."},
            {name: "Not Coded", colClass: 'uncoded', sortable: true,
             tooltip: "Students who should either 1) complete the session " +
                      "or 2) be given a code explaining why they haven't."}
            // </certified study eligible students>
        ];
    };
    return {
        scope: {},
        link: function (scope, element, attrs) {
            // running sortBy sets scope.reverseSort and scope.sortedColumn
            scope.sortBy = sortByFactory(scope, element, 'tr');
            scope.sortIconClass = sortIconClassFactory(scope);
        },
        controller: controller,
        templateUrl: '/static/dashboard_widgets/cohort_progress_list.html'
    };
});

// Displays statistics of *one or more* cohorts, broken down by activity
// ordinal. Used in two dashboard views: program_progress and cohort_progress.
PertsApp.directive('aggregateCohortProgress', function () {
    'use strict';
    return {
        scope: {
            showCohortColumn: '@showCohortColumn',
            cohortIds: '@cohortIds',
            activityOrdinal: '@activityOrdinal',
            name: '@name',
            sessions: '=',
            filterText: '='
        },
        controller: function ($scope, $getStore, $window) {
            $scope.data = {all: {}, certified: {}};

            $scope.$watch('cohortIds', function (value) {
                if (value) {
                    value = $scope.$eval(value);
                    $scope.cohortList = $getStore.getList(value);
                }
            });
            $scope.$watch('cohortList', function () {
                var allLoaded = true;
                forEach($scope.cohortList, function (cohort) {
                    if (!cohort.name) {
                        allLoaded = false;
                    }
                });
                if (allLoaded) {
                    $scope.aggregate();
                }
            }, true);

            // Each cohort has aggregation data. But this widget/directive
            // represents one activity ordinal out of a set of cohorts. That
            // means we need to summarize subsets of the available aggregation
            // data.
            $scope.aggregate = function () {
                // This will be the new summary
                var data;
                forEach($scope.cohortList, function (cohort) {
                    // Extract data relevant to just one activity ordinal.
                    var cData = cohort._aggregation_data[$scope.activityOrdinal] ||
                        $window.cohortAggregationDataTemplate;

                    // If the widget's data is currently blank, initialize it
                    // with whatever this current cohort has got. Otherwise,
                    // go through it and increment each stat.
                    if (data === undefined) {
                        data = angular.copy(cData);
                    } else {
                        forEach(cData, function (key1, value1) {
                            if (typeof value1 === 'number') {
                                data[key1] += value1;
                            } else {
                                forEach(value1, function (key2, value2) {
                                    data[key1][key2] += value2;
                                });
                            }
                        });
                    }
                });

                // Now that the (potentially) multiple cohorts have been
                // aggregated, calculate the stats users actually want to see.
                $scope.unscheduled = data.unscheduled;
                $scope.behind = data.behind;
                $scope.scheduledCompleted = data.scheduled + data.completed;
                $scope.totalClassrooms = data.unscheduled + data.behind +
                                         data.completed + data.scheduled;

                $scope.incompleteRosters = data.incomplete_rosters;
                $scope.uncertified = data.total_students - data.certified_students;

                $scope.studyEligible = data.certified_study_eligible_dict.n;
                $scope.completed = data.certified_study_eligible_dict.completed;
                $scope.pctCompleted = getPercentString(
                    $scope.completed, $scope.studyEligible);
                $scope.makeupIneligible = data.certified_study_eligible_dict.makeup_ineligible;
                $scope.makeupEligible = data.certified_study_eligible_dict.makeup_eligible;
                $scope.uncoded = data.certified_study_eligible_dict.uncoded;
            };

            $scope.pctStartedCompleted = function () {
                if (!$scope.data) { return; }
                return getPercentString($scope.data.all.completed,
                                        $scope.data.all.started);
            };

            $scope.pctStartedCertified = function () {
                if (!$scope.data) { return; }
                return getPercentString($scope.data.certified.started,
                                        $scope.data.all.started);
            };

            $scope.pctCertifiedCompleted = function () {
                if (!$scope.data) { return; }
                return getPercentString($scope.data.certified.completed,
                                        $scope.data.certified.total);
            };

            $scope.pctCertifiedAccountedFor = function () {
                if (!$scope.data) { return; }
                return getPercentString($scope.data.certified.accounted_for,
                                        $scope.data.certified.total);
            };

        },
        link: function (scope, element, attrs) {
            watchFilter(scope, element);
        },
        templateUrl: '/static/dashboard_widgets/aggregate_cohort_progress.html'
    };
});

PertsApp.directive('classroomEntryList', function () {
    'use strict';
    return {
        scope: {},
        controller: function ($scope, $getStore, $pertsAjax) {
            $scope.rows = [];
            $scope.classroomList = [$getStore.get($scope.$root.entityId)];
            // load all the teachers of these classrooms
            var classroomIds = forEach($scope.classroomList, function (c) {
                return c.id;
            });
            $pertsAjax({
                url: '/api/get/user',
                params: {
                    user_type_json: ['teacher', 'school_admin'],
                    owned_classroom_list_json: classroomIds
                }
            }).then(function (response) {
                $getStore.setList(response);
                forEach($scope.classroomList, function (classroom) {
                    var row = {classroom: classroom.id};
                    forEach(response, function (teacher) {
                        if (teacher.owned_classroom_list.contains(classroom.id)) {
                            row.teacher = teacher.id;
                        }
                    });
                    $scope.rows.push(row);
                });
            });
        },
        templateUrl: '/static/dashboard_widgets/classroom_entry_list.html'
    };
});

PertsApp.directive('classroomEntry', function () {
    'use strict';
    return {
        scope: {
            adminOptions: '@adminOptions',
            classroomId: '@classroomId',
            teacherId: '@teacherId'
        },
        controller: function ($scope, $getStore, $pertsAjax, $window) {
            $scope.$watch('classroomId + teacherId + adminOptions',
                          function (value) {
                if ($scope.classroomId === undefined ||
                    $scope.teacherId === undefined) {
                    return;
                }
                $scope.classroom = $getStore.get($scope.classroomId);
                $scope.teacher = $getStore.get($scope.teacherId);

                // if adminOptions is true (which is only the case on the
                // dashboard, not in other places this widget is used, like a
                // teacher panel) then look up who else we might want to assign
                // this classroom to as owner.
                if ($scope.adminOptions === 'true') {
                    // Because of our clever permissions-based filtering, we
                    // can be confident users can't re-assign inappropriately.
                    // We do want to limit to the current cohort so the list
                    // isn't too huge.
                    $pertsAjax({
                        url: '/api/get/user',
                        params: {
                            user_type_json: ['teacher', 'school_admin'],
                            assc_cohort_list: $scope.$root.cohort.id
                        }
                    }).then(function (data) {
                        $scope.otherAdmins = forEach(data, function (admin) {
                            // filter out the current teacher
                            if (admin.id !== $scope.teacher.id) {
                                return admin;
                            }
                        });
                    });
                }
            });
            $scope.deleteClassroom = function () {
                if (confirm("Are you sure you want to delete " + $scope.classroom.name + "?")) {
                    var url = '/api/delete/classroom/' + $scope.classroom.id;
                    $pertsAjax({url: url}).then(function () {
                        $window.location.reload();
                    });
                }
            };
            $scope.reassignClassroom = function () {
                // Someone with sufficient permission wants to change the owner
                // of this classroom. That means we need to:
                // * Break relationships
                //   - from old owner to classroom
                //   - from classroom to old owner
                // * Create relationships
                //   - from new owner to classroom
                //   - from classroom to new owner

                $pertsAjax({
                    url: '/api/disown/user/' + $scope.teacher.id +
                         '/classroom/' + $scope.classroom.id
                });

                $pertsAjax({
                    url: '/api/set_owner/user/' + $scope.newOwner.id +
                         '/classroom/' + $scope.classroom.id
                });

                // Chain these two so that the second doesn't take effect
                // before the first. Otherwise the unassociate call may be
                // overridden by the associate call, resulting in a double
                // association.
                $pertsAjax({
                    url: '/api/unassociate/classroom/' + $scope.classroom.id +
                         '/user/' + $scope.teacher.id
                }).then(function () {
                    $pertsAjax({
                        url: '/api/associate/classroom/' + $scope.classroom.id +
                             '/user/' + $scope.newOwner.id
                    }).then(function () {
                        $window.location.reload();
                    });
                });
            };
        },
        templateUrl: '/static/dashboard_widgets/classroom_entry.html'
    };
});

// Displays statistics broken down by classroom for all the classrooms in a
// cohort. Calls classroomProgress for each item in the list.
PertsApp.directive('classroomProgressList', function () {
    'use strict';
    return {
        scope: {},
        controller: function ($scope, $q, $seeStore, $getStore, $pertsAjax, $forEachAsync, $modal, $window, $sce) {
            // If redirection gets this deep, it should stop.
            $scope.$root.redirecting = false;

            $scope.selectedClassrooms = [];

            $scope.classroomParams = {};

            // Group activities by classroom, sorting by activities by
            // ordinal. Sorting by classroom name is taken care of in the
            // markup.
            $scope.indexClassrooms = function (activityList) {
                var index = {};
                forEach(activityList, function (a) {
                    var cId = a.assc_classroom_list[0];
                    util.initProp(index, cId, {activityList: []});
                    index[cId].activityList.push(a);
                    index[cId].classroomName = $getStore.get(cId).name;
                });
                forEach(index, function (cId, cInfo) {
                    cInfo.activityList.sort(function (a, b) {
                        return a.activity_ordinal - b.activity_ordinal;
                    });
                });

                $scope.classroomIndex = index;
            };

            // Get al the classrooms in this cohort.
            $pertsAjax({
                url: '/api/get/classroom',
                params: {
                    assc_cohort_list: $scope.$root.currentEntity.id
                }
            }).then(function (response) {
                $scope.classroomList = $getStore.setList(response);

                // pre-load all the activities from this cohort
                $pertsAjax({
                    url: '/api/get/activity',
                    params: {
                        user_type: 'student',
                        assc_cohort_list: $scope.$root.currentEntity.id
                    }
                }).then(function (response) {
                    // Store activities.
                    $scope.studentActivityList = $getStore.setList(response);
                    // Index them by classroom and do some sorting.
                    $scope.indexClassrooms($scope.studentActivityList);
                });
            });

            // See the other cohorts in this program we can move classrooms and
            // students into; it will be used to populate the move menu.
            $scope.$watch('$root.program', function (program) {
                if (!program) { return; }

                var programInfo = $window.programInfo[program.id];
                $scope.aliasSchoolInstructions = $sce.trustAsHtml(
                    programInfo.alias_school_instructions);
                $scope.normalSchoolInstructions = $sce.trustAsHtml(
                    programInfo.normal_school_instructions);

                // Read sessions from server's program config and determine the
                // number of session rows the student needs.
                var studentOutline = $window.programInfo[program.id].student_outline;
                $scope.sessions = forEach(studentOutline, function (module) {
                    if (module.type === 'activity') {
                        return module;
                    }
                });

                var params = {assc_program_list: program.id};
                if ($scope.$root.userType !== 'god') {
                    // For non-gods, see the user's OWNED cohorts in this program.
                    params.id_json = $window.user.owned_cohort_list;
                }
                $pertsAjax({
                    url: '/api/see/cohort',
                    params: params
                }).then(function (response) {
                    // Remove *this* cohort from the list b/c it doesn't
                    // make sense to move from and to the same place.
                    var cList = forEach(response, function (c) {
                        if (c.id !== $scope.$root.currentEntity.id) { return c; }
                    });
                    $scope.availableCohorts = $seeStore.setList(cList);
                });
            });

            // Detect users clicking on the "move classroom to cohort" menu,
            // confirm their choice, and launch the moving function.
            $scope.$watch('moveToCohort', function (cohort) {
                if (!cohort) { return; }
                var msg = "Are you sure you want to move " +
                          $scope.selectedClassrooms.length + " classrooms to " +
                          cohort.name + "?" +
                          "\n\n" +
                          "This process will take about a minute. It is " +
                          "important not to leave the page before it is " +
                          "complete.";
                if (confirm(msg)) {
                    $scope.moveClassrooms($scope.selectedClassrooms, cohort);
                } else {
                    $scope.moveToCohort = undefined;
                }
            });

            // Put in a kinda-crappy replacement of an input placeholder for
            // browsers which don't support placeholders.
            // The timeout lets us escape angular's digest loop, so setting
            // the value of the input *won't* be recognized as an actual
            // attempt to search, which is what we want.
            if (!util.weHas.placeholder()) {
                setTimeout(function () {
                    $('.dashboard-table-controls [placeholder]').val('Search...');
                }, 1);
            }

            $scope.printSessionInstructions = function () {
                var newWindow = window.open($scope.sessionInstructionsUrl());
                newWindow.print();
            };

            $scope.moveClassrooms = function (classroomIds, newCohort) {
                $scope.showMoveProgressMonitor = true;
                $scope.totalMovedClassrooms = classroomIds.length;
                $scope.totalMovedStudents = 0;
                $scope.numMovedClassrooms = 0;
                $scope.numMovedStudents = 0;

                // Moving classrooms is so rare, we want to be alerted to it.
                var logMove = function (msg) {
                    $pertsAjax({
                        url: '/api/log/error',
                        params: {
                            message: msg,
                            classrooms: classroomIds,
                            original_cohort: $scope.$root.cohort.id,
                            new_cohort: newCohort.id
                        }
                    });
                };

                logMove("This isn't necessarily an error; it's a hack to " +
                        "notify ourselves about a potentially sensitive " +
                        "operation: a user attempting to move classroom(s). " +
                        "Check for a follow-up message on the result.");

                var moveSingleStudent = function (student) {
                    // It is important to unassociate the student from the
                    // cohort FIRST (before associating them to the new one),
                    // because it also (like associate) cascades the change
                    // through higher entities. Doing it second would erase any
                    // higher associations that overlap with the new
                    // association, like the program.

                    // tl;dr: if you don't do it this way, you get a student
                    // who has no program.

                    return $pertsAjax({
                        url: '/api/unassociate/user/' + student.id +
                             '/cohort/' + $scope.$root.cohort.id
                    }).then(function (response) {
                        return $pertsAjax({
                            url: '/api/associate/user/' + student.id +
                                 '/cohort/' + newCohort.id
                        }).then(function () {
                            $scope.numMovedStudents += 1;
                        });
                    });
                };

                // Get all the students in all these classroom, then
                // reassociate each of them.
                var moveStudentsPromise = $pertsAjax({
                    url: '/api/see/user',
                    params: {assc_classroom_list_json: classroomIds}
                }).then(function (students) {
                    $scope.totalMovedStudents = students.length;
                    return $forEachAsync(students, moveSingleStudent, 'serial');
                });

                // Also reassociate the classrooms themselves.
                var moveSingleClassroom = function (classroomId) {
                    // It is important to unassociate the classroom from the
                    // cohort FIRST (before associating them to the new one),
                    // because it also (like associate) cascades the change
                    // through higher entities. Doing it second would erase any
                    // higher associations that overlap with the new
                    // association, like the program.

                    // tl;dr: if you don't do it this way, you get a classroom
                    // which has no program.

                    return $pertsAjax({
                        url: '/api/unassociate/classroom/' + classroomId +
                             '/cohort/' + $scope.$root.cohort.id
                    }).then(function (response) {
                        return $pertsAjax({
                            url: '/api/associate/classroom/' + classroomId +
                                 '/cohort/' + newCohort.id
                        }).then(function () {
                            $scope.numMovedClassrooms += 1;
                        });
                    });
                };

                var moveClassroomsPromise = $forEachAsync(
                    classroomIds, moveSingleClassroom, 'serial');

                // If anything goes wrong with the whole move, the
                // errorCallback() will trigger.
                $q.all([moveStudentsPromise, moveClassroomsPromise]).then(
                    function successCallback() {
                        $scope.showMoveProgressMonitor = false;

                        $scope.selectedClassrooms = [];
                        // remove those classrooms' activities from the list
                        $scope.studentActivityList = forEach($scope.studentActivityList, function (a) {
                            if (!classroomIds.contains(a.assc_classroom_list[0])) {
                                return a;
                            }
                        });

                        logMove('classroom(s) were successfully moved');
                    },
                    function errorCallback() {
                        $scope.displayMoveError = true;
                        logMove('classroom(s) were NOT successfully moved');
                    }
                );
            };

            $scope.columns = [
                {name: "", colClass: "select", sortable: false,
                 tooltip: ""},
                {name: "Class Name", colClass: "name", sortable: true,
                 tooltip: ""},
                {name: "#", colClass: "session", sortable: true,
                 tooltip: "Session Number"},
                {name: "Date", colClass: "date", sortable: true,
                 tooltip: "When the session is scheduled to be done."},
                {name: "Status", colClass: "status", sortable: true,
                 tooltip: ""},
                {name: "Study Inelg", colClass: 'study_ineligible', sortable: true,
                 tooltip: "Study Ineligible: students with a participation code that makes " +
                          "them ineligible for the study."},
                {name: "Study Elg", colClass: 'certified', sortable: true,
                 tooltip: "All study eligible students."},
                {name: "Cmpl", colClass: 'completed', sortable: true,
                 tooltip: "Complete: students who have completed the session, as a percent of study eligible students."},
                {name: "Makeup Inelg", colClass: 'makeup_ineligible', sortable: true,
                 tooltip: "Makeup Ineligible: students who may NOT participate in a make up session."},
                {name: "Makeup Elg", colClass: 'makeup_eligible', sortable: true,
                 tooltip: "Makeup Eligible: students who MAY participate in a make up session."},
                {name: "Not Coded", colClass: 'uncoded', sortable: true,
                 tooltip: "Students who should either 1) complete the session " +
                          "or 2) be given a code explaining why they haven't."}
            ];

            $scope.constructNewClassroomName = function () {
                var p = $scope.classroomParams;
                if ([p.name, p.teacher_first_name, p.teacher_last_name].contains(undefined)) {
                    return '';
                }
                var firstInitial = p.teacher_first_name.substr(0, 1);
                var paren = p.name_extra ? ' (' + p.name_extra + ')' : '';

                return p.teacher_last_name + ' ' + firstInitial + '. - ' +
                       p.name + paren;
            };

            $scope.addClassroom = function (classroomParams) {
                // takes a javascript object,
                // {name: 'English 101', teacher: userObject}
                $scope.showAddForm = false;  // close the form
                $pertsAjax({
                    url: '/api/put/classroom',
                    params: {
                        program: $scope.$root.program.id,
                        cohort: $scope.$root.cohort.id,
                        name: $scope.constructNewClassroomName(),
                        user: $window.userId,
                        teacher_name: classroomParams.teacher_first_name + ' ' + classroomParams.teacher_last_name,
                        teacher_email: classroomParams.teacher_email
                    }
                }).then(function (classroom) {
                    classroom = $getStore.set(classroom);
                    $scope.classroomList =
                        $scope.classroomList.concat(classroom);

                    var newActivities = $getStore.setList(
                        classroom._student_activity_list);
                    // add it to the user list to it gets a row widget
                    $scope.studentActivityList =
                        $scope.studentActivityList.concat(newActivities);

                    $scope.indexClassrooms($scope.studentActivityList);
                });
            };

            $scope.confirmDeleteClassrooms = function () {
                // Make sure they didn't click by mistake.
                var msg = "Are you sure you want to delete " +
                    $scope.selectedClassrooms.length + " classrooms?";
                if (!confirm(msg)) { return; }

                // First check to see if there are any students in these
                // classrooms. Only allow empty classrooms to be deleted.
                $pertsAjax({
                    url: '/api/get/user',
                    params: {
                        user_type: 'student',
                        assc_classroom_list_json: $scope.selectedClassrooms
                    }
                }).then(function (students) {
                    if (students.length > 0) {
                        alert("There are still students in some of these " +
                              "classrooms. You may only delete empty " +
                              "classrooms.");
                    } else {
                        $scope.deleteSelectedClassrooms();
                    }
                });
            };

            $scope.deleteSelectedClassrooms = function (classroomId) {
                // Delete each classroom one by one.
                $forEachAsync($scope.selectedClassrooms, function (classroomId) {
                    return $pertsAjax({url: '/api/delete/classroom/' + classroomId});
                }, 'serial').then(function () {
                    // Rebuild the list of displayed activities based on which
                    // ones didn't just have their classrooms deleted.
                    $scope.studentActivityList = forEach($scope.studentActivityList, function (a) {
                        if (!$scope.selectedClassrooms.contains(a.assc_classroom_list[0])) {
                            return a;
                        }
                    });
                    // Uncheck all the select boxes.
                    $scope.selectedClassrooms = [];
                });
            };

            // Build a dialog box for displaying email addresses of selected users.
            $scope.openDialog = function () {
                var testingDialogMarkup = '' +
                    '<div class="modal-header">' +
                        '<h3>Email Addresses: paste into "To:" field</h3>' +
                    '</div>' +
                    '<div class="modal-body">' +
                        '<p>' +
                            forEach($scope.classroomList, function (c) {
                                if ($scope.selectedClassrooms.contains(c.id)) {
                                    return c.teacher_email;
                                }
                            }).join(', ') +
                        '</p>' +
                    '</div>' +
                    '<div class="modal-footer">' +
                        '<button ng-click="close()" class="btn btn-default">' +
                            'Close' +
                        '</button>' +
                    '</div>';
                // See angular-ui docs for details on available options.
                // http://angular-ui.github.io/bootstrap/#/modal
                var modalInstance = $modal.open({
                    backdrop: true,
                    keyboard: true,
                    backdropClick: true,
                    backdropFade: true,
                    template:  testingDialogMarkup,
                    controller: function ($scope, $modalInstance) {
                        $scope.close = function () {
                            $modalInstance.dismiss('close');
                        };
                    }
                });
            };

            $scope.trackSelection = function (event, classroomId, isSelected) {
                if (
                    isSelected === true &&
                    !$scope.selectedClassrooms.contains(classroomId)
                ) {
                    $scope.selectedClassrooms.push(classroomId);
                } else if (isSelected === false) {
                    $scope.selectedClassrooms.remove(classroomId);
                }

                // Broadcast the change down to activity rows again, so sibling
                // activities can stay in sync (b/c they both together
                // represent the selected classroom).
                $scope.$broadcast('/classroomProgressList/selectionChange',
                                  classroomId, isSelected);
            };

            $scope.toggleSelectAll = function (checked) {
                $scope.$broadcast('/classroomProgressList/toggleSelectAll', checked);
            };

            // Listen to rows whose checkboxes change and track them.
            $scope.$on('/activityProgress/selectionChange',
                       $scope.trackSelection);
        },
        link: function (scope, element, attrs) {
            // running sortBy sets scope.reverseSort and scope.sortedColumn
            var table = element.children('table').get();
            scope.sortBy = sortByFactory(scope, table, 'tbody');
            scope.sortIconClass = sortIconClassFactory(scope);
        },
        templateUrl: '/static/dashboard_widgets/classroom_progress_list.html'
    };
});

// Displays statistics for a given activity.
PertsApp.directive('activityProgress', function () {
    'use strict';
    return {
        scope: {
            id: '@activityId',
            showProgress: '@showProgress',
            sessions: '=',
            filterText: '='
        },
        controller: function ($scope, $getStore, $scheduleRules, $timeout, $window) {
            var module;
            $scope.dateValid = undefined;

            // The appropriate incomplete text label (e.g. "unscheduled")
            // will be updated in a $watch of the activity's scheduled date.
            $scope.statusOptions = [
                {value: 'incomplete', text: ''},
                {value: 'completed', text: 'completed'}
            ];

            $scope.$watch('id + $root.program', function () {
                if (!$scope.id || !$scope.$root.program) { return; }
                //// a bunch of logic that depends on knowing the activity
                $scope.activity = $getStore.get($scope.id);

                // Used to display the classroom name
                $scope.classroom = $getStore.get($scope.activity.assc_classroom_list[0]);

                $scope.processScheduling();

                $scope.calculateStats();
            }, true);

            // These variables control styling and tooltip text of certain
            // table fields, which change based on various conditions.
            var resetWarnings = function () {
                $scope.certClass = '';
                $scope.unaccountedClass = '';
                $scope.mysteryClass = '';
                $scope.certTooltip = '';
                $scope.unaccountedTooltip = '';
                $scope.mysteryTooltip = '';
            };
            resetWarnings();
            // Monitor activity status and update styling and tooltips.
            $scope.$watch('activity.status', function (status) {
                if (status === 'completed') {
                    if (!$scope.classroom.roster_complete) {
                        $scope.certClass = 'warning';
                        $scope.certTooltip = "Roster not complete.";
                    }
                    if ($scope.uncertified > 0) {
                        $scope.uncertifiedClass = 'warning';
                        $scope.uncertifiedTooltip = "Students have signed in with unexpected names.";
                    }
                    if ($scope.makeupEligible > 0) {
                        $scope.makeupEligibleClass = 'warning';
                        $scope.makeupEligibleTooltip = "These students should make up the session.";
                    }
                    if ($scope.uncoded > 0) {
                        $scope.uncodedClass = 'warning';
                        $scope.uncodedTooltip = "Students who haven't finished the session should be given a non-participation code.";
                    }
                } else {
                    resetWarnings();
                }
            });

            // Announce changes to the selected checkbox to the table.
            $scope.$watch('isSelected', function (isSelected) {
                if (!$scope.classroom) { return; }
                $scope.$emit('/activityProgress/selectionChange',
                             $scope.classroom.id, isSelected);
            });

            $scope.$on('/classroomProgressList/selectionChange', function (event, classroomId, isSelected) {
                if ($scope.classroom && $scope.classroom.id === classroomId) {
                    $scope.isSelected = isSelected;
                }
            });

            $scope.$on('/classroomProgressList/toggleSelectAll', function (event, checked) {
                $scope.isSelected = checked;
            });

            $scope.$watch('dateValid', function () {
                if ($scope.dateValid === false) {
                    $scope.datepickrTooltip = "This date conflicts with the " +
                        "other session(s).";
                } else {
                    $scope.datepickrTooltip = "";
                }
            });

            var schedulingProcessed = false;
            $scope.processScheduling = function () {
                if (schedulingProcessed) { return; }
                schedulingProcessed = true;
                // determine which part of the program config is relevant
                var programId = $scope.activity.assc_program_list[0];
                var userType = $scope.activity.user_type;
                var outline = $window.programInfo[$scope.$root.program.id][userType + '_outline'];
                forEach(outline, function (m) {
                    if (m.activity_ordinal === $scope.activity.activity_ordinal && m.type === 'activity') {
                        module = m;
                    }
                });

                // interpret relative open date logic
                if (module.date_open_relative_to) {
                    // watch the referenced activities so we can dynamically
                    // adjust what dates are available
                    $scheduleRules.watch($scope.classroom.id, module.date_open_relative_to, function (date) {
                        var interval = module.date_open_relative_interval * Date.intervals.day;
                        // An activity is open if BOTH the relative delay is
                        // satisfied AND the absolute open date has passed. So
                        // a given date is valid if it is later than BOTH of
                        // these.
                        var relativeDateOpen = new Date(date.getTime() + interval);
                        var absoluteDateOpen = Date.createFromString(module.date_open, 'local');
                        var dateOpen = new Date(Math.max(relativeDateOpen, absoluteDateOpen));

                        $scope.datepickr.config.dateOpen = dateOpen.toDateString('local');

                        // the calendar's constraints have changed in response
                        // to others being set; re-draw
                        $scope.dateValid = $scope.datepickr.rebuild();

                    });
                } else {
                    $scope.datepickr.config.dateOpen = module.date_open;
                }


                // interpret relative close date logic
                if (module.date_closed_relative_to) {
                    // watch the referenced activities so we can dynamically
                    // adjust what dates are available
                    $scheduleRules.watch($scope.classroom.id, module.date_closed_relative_to, function (date) {
                        var interval = module.date_closed_relative_interval * Date.intervals.day;
                        // The effective closed date is either the relative
                        // close interval or the absolute close date, whichever
                        // is sooner.
                        var relativeDateClosed = new Date(date.getTime() + interval);
                        var absoluteDateClosed = Date.createFromString(module.date_closed, 'local');
                        var dateClosed = new Date(Math.min(relativeDateClosed, absoluteDateClosed));

                        $scope.datepickr.config.dateClosed = dateClosed.toDateString('local');

                        // the calendar's constraints have changed in response
                        // to others being set; re-draw
                        $scope.dateValid = $scope.datepickr.rebuild();
                    });
                } else {
                    $scope.datepickr.config.dateClosed = module.date_closed;
                }

                // the calendar has initial constraints (based purely on page-
                // load information) which it didn't have when it was first
                // instantiated in the link() function; re-draw.
                $scope.dateValid = $scope.datepickr.rebuild();

                // monitor the calendar widget and send its value into the
                // the activity when it changes; the getStore will do the put.
                $scope.$watch('datepickr._currentValue', function () {
                    var date = $scope.datepickr.getValue();
                    if (date) {
                        $scope.activity.scheduled_date = date.toDateString('local');
                    }
                });

                if ($scope.activity.scheduled_date) {
                    // if the activity as loaded is already scheduled, tell the
                    // calendar widget
                    var date = Date.createFromString(
                        $scope.activity.scheduled_date, 'local');
                    $scope.datepickr.setDate(date);
                    // send an initial update to listening widgets that this
                    // activity knows its date; further updates will come
                    // from watching the data model
                    $scope.$emit('activitySchedule/scheduledAs',
                                 $scope.id, $scope.activity.scheduled_date);
                }

            };

            // It's critical that the $watch set here, which will communicate
            // the calendar's value to the $scheduleRules service, only be
            // called AFTER all other widgets have had a chance to set up their
            // watchers with that service. Otherwise, widgets will not render
            // correctly on page load because their watchers will not be called
            // initially. The necessary delay is accomplished with this
            // timeout.
            $timeout(function () {
                // when the activity's date changes
                $scope.$watch('activity.scheduled_date', function (dateString) {
                    if (dateString) {
                        var dateObject = Date.createFromString(dateString, 'local');

                        // update the copy of dates that all widgets can see,
                        // so they can adjust their dynamic constraints
                        $scheduleRules.addDate($scope.activity, dateObject);

                        $scope.datepickr.setDate(dateObject);

                        // the user has changed the value of this calendar, it
                        // may have become valid or invalid in response; re-
                        // draw
                        $scope.dateValid = $scope.datepickr.rebuild();

                        // and inform the steps, which are waiting for all
                        // activities to be scheduled before moving on
                        $scope.$emit('activitySchedule/scheduled');
                    }

                    // Update the text label of the status dropdown.
                    var statusText = getInterpretedStatus($scope.activity,
                                                          'incomplete');
                    $scope.statusOptions[0].text = statusText;

                    // IE, that saintly savant of browsers, doesn't know how
                    // to update the displayed value of a select if it options
                    // change dynamically. Force it to update its display by
                    // waiting for the angular digest loop to complete and then
                    // writing the text directly to the DOM.
                    $timeout(function () {
                        $('tr[activity-id="' + $scope.id + '"] .status select').each(function (index, selectNode) {
                            selectNode.options[0].text = statusText;
                        }).trigger('change');
                    }, 1);
                }, true);
            }, 1);

            $scope.interpretedStatus = getInterpretedStatus;

            $scope.calculateStats = function () {

                var data = $scope.activity._aggregation_data;
                var studyEligibleData = data.certified_study_eligible_dict;


                $scope.uncertified = data.total_students - data.certified_students;
                $scope.studyIneligible = data.certified_students - studyEligibleData.n;
                $scope.studyEligible = studyEligibleData.n;
                $scope.completed = studyEligibleData.completed;
                $scope.pctCompleted = getPercentString(
                    studyEligibleData.completed, studyEligibleData.n);
                $scope.makeupIneligible = studyEligibleData.makeup_ineligible;
                $scope.makeupEligible = studyEligibleData.makeup_eligible;
                $scope.uncoded = studyEligibleData.uncoded;

                // $scope.pctStartedCompleted = getPercentString(
                //     data.all.completed, data.all.started);
            };
        },
        link: function (scope, element, attrs) {
            // create datepickers
            var node = $('.datepickr', element).get(0);
            // Although it would be nice to rely on Date.toLocaleDateString(),
            // IE likes to use the verbose style, e.g. "Wednesday, July 23rd,
            // 2014", and we need a compact representation.
            // var config = {dateFormat: 'byLocale'};
            // So instead we manually format it in compact US-style as
            // 1-or-2 digit month / 1-or-2 digit day / 2 digit year
            var config = {dateFormat: 'n/j/y'};
            scope.datepickr = new datepickr(node, config);
            element.addClass('activity-progress');

            // Activity rows are grouped by classroom into tbody tags.
            // We want to filter at that level, so that a given tbody is
            // switched on or off as a whole by the filter next. To do this,
            // simply provide the tbody to the watch function. All table cells
            // in the tbody will be converted to a string, which will be
            // matched against the filter text. Then each activity widget in
            // the tbody will receive the same signal: match or no match, and
            // the whole set will turn on or off as a coordinated group.
            watchFilter(scope, element.parent());

            scope.$watch('activity.scheduled_date', function (dateString) {
            });
        },
        templateUrl: '/static/dashboard_widgets/activity_progress.html'
    };
});

PertsApp.directive('rosterTable', function () {
    'use strict';
    var controller = function ($scope, $seeStore, $getStore, $pertsAjax, $location, $forEachAsync, $window) {
        $scope.selectedUsers = [];
        $scope.userList = [];

        $scope.summaryColumns = [
            {name: "Session", colClass: 'session'},
            // "Total" is really certified students, but all students are
            // certified!
            {name: "Total", colClass: 'total',
             tooltip: "Total students in the classroom."},
            {name: "Study Ineligible", colClass: 'study_ineligible',
             tooltip: "Students with a non-participation code that makes " +
                      "them ineligible for the study."},
            {name: "Completed", colClass: 'completed',
             tooltip: "Students who have completed the session (100% progress)."},
            {name: "Make-Up Ineligible", colClass: 'makeup_ineligible',
             tooltip: "Students who may NOT participate in a make up session."},
            {name: "Make-Up Eligible", colClass: 'makeup_eligible',
             tooltip: "Students who MAY participate in a make up session."},
            {name: "Uncoded", colClass: 'uncoded',
             tooltip: "Students who should either 1) complete the session " +
                      "or 2) be given a code explaining why they haven't."}
        ];

        $scope.columns = [
            {name: "", colClass: 'select', sortable: false, tooltip: ""},
            {name: "First Name", colClass: 'first_name', sortable: true, tooltip: ""},
            {name: "Last Name", colClass: 'last_name', sortable: true, tooltip: ""},
            {name: "Session - Progress%", colClass: 'session_progress', sortable: false, tooltip: ""},
            // the css class 'progress' collides with bootstrap
            // {name: "Progress", colClass: 'progress_pd', sortable: false, tooltip: ""},
            {name: "Participation Code", colClass: 'status_code', sortable: false, tooltip: ""}
        ];

        // Columns vary a little according to dashboard level.
        var certifiedColumn = {name: "Certified?", colClass: 'cert',
            sortable: true, tooltip: ""};
        var classroomColumn = {name: "Classroom", colClass: 'classroom',
            sortable: true, tooltip: ""};

        var params = {user_type: 'student', order: 'last_name'};
        if ($scope.$root.level === 'classroom') {
            // At the classroom we want only students within the current
            // classroom
            params.assc_classroom_list = $scope.$root.currentEntity.id;
        } else if ($scope.$root.level === 'cohort') {
            // At the cohort level, instead of a certified setter, there's
            // a link to the student's classroom.
            $scope.columns.splice(1, 0, classroomColumn);
            params.assc_cohort_list = $scope.$root.currentEntity.id;
        }

        // Get all the users in this classroom so we can build the roster.
        $pertsAjax({
            url: '/api/get/user',
            params: params
        }).then(function (response) {
            $scope.userList = $getStore.setList(response);
        });

        // Read sessions from server's program config and determine the
        // number of session rows the student needs.
        $scope.$watch('$root.program', function (program) {
            if (!program) { return; }
            var studentOutline = $window.programInfo[program.id].student_outline;
            $scope.sessions = forEach(studentOutline, function (module) {
                if (module.type === 'activity') {
                    return module;
                }
            });
            // Watch changes to user properties, and calculate stats on who's
            // certified or not.
            $scope.$watch('userList', function () {
                if (!$scope.userList) { return; }
                $scope.summary = {};
                forEach($scope.sessions, function (s) {
                    var o = s.activity_ordinal;
                    $scope.summary[o] = $scope.summarizeStudents($scope.userList, o);
                });
            }, true);
        });


        // Get all the classrooms from this cohort so we can populate
        // the moving dropdown.
        $scope.$watch('$root.cohort', function (cohort) {
            if (!cohort) { return; }
            $pertsAjax({
                url: '/api/see/classroom',
                params: {
                    assc_cohort_list: cohort.id
                }
            }).then(function (response) {
                var cList = $seeStore.setList(response);
                // Remove *this* classroom from the list (if this is the
                // classroom level) b/c it doesn't make sense to move from
                // and to the same place.
                if ($scope.classroom) {
                    $scope.availableClassrooms = forEach(cList, function (c) {
                        if (c.id !== $scope.classroom.id) { return c; }
                    });
                } else {
                    $scope.availableClassrooms = cList;
                }
            });
        });

        // Put in a kinda-crappy replacement of an input placeholder for
        // browsers which don't support placeholders.
        // The timeout lets us escape angular's digest loop, so setting
        // the value of the input *won't* be recognized as an actual
        // attempt to search, which is what we want.
        if (!util.weHas.placeholder()) {
            setTimeout(function () {
                // For the roster search field.
                $('.dashboard-table-controls [placeholder]').val('Search...');
                // For the add-students dialog.
                $('form[name="addSingleUserForm"] input[placeholder="first name"]').val('first name');
                $('form[name="addSingleUserForm"] input[placeholder="middle initial"]').val('middle_initial');
                $('form[name="addSingleUserForm"] input[placeholder="last name"]').val('last name');
                $('form[name="addCsvUsersForm"] textarea').val('first_name	middle_initial	last_name');
            }, 1);
        }

        // Very similar to the summarize_students method of the
        // Aggregator, but calculates extra stuff desired in the view.
        $scope.summarizeStudents = function (students, activityOrdinal) {
            var sessionSummary = {
                uncertified: 0,
                certified: 0,
                studyIneligible: 0,
                studyEligible: 0,
                completed: 0,
                makeupIneligible: 0,
                makeupEligible: 0,
                uncoded: 0
            };

            forEach(students, function (user) {
                // Certain students aren't counted at all, regardless of the
                // current activityOrdinal.
                var excludeStudent = false;
                forEach(user.status_codes, function (o, code) {
                    var info = $window.statusCodes[code];
                    if (info && info.exclude_from_counts) {
                        excludeStudent = true;
                    }
                });
                if (excludeStudent) {
                    // These students aren't counted at all.
                    return;
                }

                var aggData = user._aggregation_data[activityOrdinal] || {};
                var statusCode = user.status_codes[activityOrdinal];

                if (user.certified) {
                    sessionSummary.certified += 1;
                } else {
                    sessionSummary.uncertified += 1;
                    // Uncertified students aren't counted in any other
                    // category.
                    return;
                }

                if (statusCode) {
                    var status = $window.statusCodes[statusCode];
                    if (!status.study_eligible) {
                        // Don't count this student in any other categories.
                        // Skip to next one.
                        sessionSummary.studyIneligible += 1;
                        return;
                    }

                    if (status.counts_as_completed) {
                        sessionSummary.completed += 1;
                    } else if (status.makeup_eligible) {
                        sessionSummary.makeupEligible += 1;
                    } else {
                        sessionSummary.makeupIneligible += 1;
                    }
                } else if (aggData.progress === 100) {
                    sessionSummary.completed += 1;
                } else {
                    sessionSummary.uncoded += 1;
                }

                sessionSummary.studyEligible += 1;
            });

            return sessionSummary;
        };

        $scope.rosterCompleteDate = function () {
            if (!$scope.classroom || !$scope.classroom.roster_completed_datetime) {
                // Don't freak out if the classroom isn't loaded yet.
                return;
            }
            var dateStr = $scope.classroom.roster_completed_datetime;
            var date = Date.createFromString(dateStr, 'UTC');
            return date.toLocaleDateString();
        };

        $scope.trackSelection = function (event, userId, isSelected) {
            if (
                isSelected === true &&
                !$scope.selectedUsers.contains(userId)
            ) {
                $scope.selectedUsers.push(userId);
            } else if (isSelected === false) {
                $scope.selectedUsers.remove(userId);
            }
        };

        $scope.toggleSelectAll = function (checked) {
            $scope.$broadcast('/rosterTable/toggleSelectAll', checked);
        };

        // Listen to rows whose checkboxes change and track them.
        $scope.$on('/rosterRow/selectionChange', $scope.trackSelection);

        $scope.deleteSelectedUsers = function () {
            if (!confirm("Are you sure you want to delete these " +
                         $scope.selectedUsers.length + " users?")) {
                return;
            }

            var deleteUser = function (userId) {
                return $pertsAjax({url: '/api/delete/user/' + userId});
            };

            var studentIds = $scope.selectedUsers.slice(0);  // copy array
            $scope.selectedUsers = [];

            // Call deleteUser() for each student to be deleted, then
            // update the view.
            $forEachAsync(studentIds, deleteUser, 'serial').then(function () {
                // Remove the deleted users from the table
                $scope.userList = forEach($scope.userList, function (u) {
                    if (!studentIds.contains(u.id)) {
                        return u;
                    }
                });
            });
        };

        $scope.addUser = function (user) {
            // takes a javascript object,
            // e.g. {first_name: 'mister', last_name: 'ed'}
            user.classroom = $scope.$root.classroom.id;
            user.user_type = 'student';
            user.certified = true;
            return $pertsAjax({
                url: '/api/put/user',
                params: user
            }).then(function (response) {
                // Add it to the get store so the row widget can connect
                // to the data. It's important to do this before adding it to
                // the scope b/c part of what getStore does is manage
                // references. The *result* of getStore.set() has its
                // references set correctly, while reponse does not.
                var newUser = $getStore.set(response);
                // add it to the user list to it gets a row widget
                $scope.userList.push(newUser);
            });
        };

        $scope.addSingleUser = function () {
            $scope.addUser($scope.newStudent).then(function () {
                // clear the text fields
                $scope.newStudent = {};
                // show visual confirmation
                $('#confirm_add_single_user').show().fadeOut(4000);
            });
        };

        $scope.addCsvUsers = function () {
            $scope.alert = false;
            $scope.addCsvUsersBusy = true;

            var sep = "\t";  // csv separator
            var requiredColumns = [
                "first_name",
                "middle_initial",
                "last_name"
            ];
            var rows = $scope.userCsv.split("\n");

            // remove the first row; make sure columns are right
            var providedColumns = rows.splice(0, 1)[0].split(sep);
            if (!util.arrayEqual(providedColumns, requiredColumns)) {
                $scope.addCsvUsersBusy = false;
                $scope.alert = {
                    type: 'danger',
                    msg: "Invalid headers. Must be tab-separated with " +
                        "columns " + requiredColumns.join("\t")
                };
            }

            // build a list of user objects
            var userList = forEach(rows, function (row) {
                var fields = row.split(sep);
                if (fields.length !== requiredColumns.length) {
                    $scope.addCsvUsersBusy = false;
                    $scope.alert = {
                        type: 'danger',
                        msg: "Invalid data. This row doesn't have " +
                            "the right number of fields: " + row
                    };
                }
                var user = {};
                forEach(requiredColumns, function (col, index) {
                    user[col] = fields[index];
                });
                return user;
            });

            if (!$scope.alert) {
                // Adding many users at once can take a long time if done one
                // by one, so POST the whole batch.
                $pertsAjax({
                    url: '/api/batch_put_user',
                    method: 'POST',
                    params: {
                        user_names: userList,
                        classroom: $scope.$root.classroom.id,
                        user_type: 'student',
                        certified: true
                    }
                }).then(function (response) {
                    // Add new users to the get store so the row widget can
                    // connect to the data. It's important to do this before
                    // adding it to the scope b/c part of what getStore does
                    // is manage references. The *result* of getStore.set()
                    // has its references set correctly, while reponse does
                    // not.
                    var newUsers = $getStore.setList(response);
                    // add it to the user list to it gets a row widget
                    $scope.userList = $scope.userList.concat(newUsers);
                    // clear the text fields
                    $scope.userCsv = '';
                    // Trigger a change event on the textarea so that the
                    // autogrow plugin can do its work.
                    setTimeout(function () {
                        $('form[name="addCsvUsersForm"] textarea').trigger('change');
                    }, 1);
                    // show visual confirmation
                    $scope.addCsvUsersBusy = false;
                    $('#confirm_add_csv_users').show().fadeOut(4000);
                });
            }
        };

        $scope.markRosterAsComplete = function () {
            // Most of these objects are linked through the getStore, so just
            // changing their properies is sufficient to save to the server.
            forEach($scope.userList, function (user) {
                user.certified = true;
            });
            $scope.classroom.roster_complete = true;
            var nowDateStr = (new Date()).toDateTimeString('UTC');
            $scope.classroom.roster_completed_datetime = nowDateStr;

            // But we need to redundantly store the roster completion on
            // related activity entities as well, and since they're not loaded
            // yet, that's more work. First look them up, then sent an update
            // request to each.
            $pertsAjax({
                url: '/api/see/activity',
                params: {
                    // Must specify a see property b/c activities don't have
                    // names, and name is the default. W/o specifying this,
                    // you would get no results.
                    see: 'id',
                    assc_classroom_list: $scope.classroom.id
                }
            }).then(function (response) {
                forEach(response, function (activity) {
                    $pertsAjax({
                        url: '/api/put/activity/' + activity.id,
                        params: {roster_complete: true}
                    });
                });
            });
        };

        // Detect users clicking on the "move student to classroom" menu,
        // confirm their choice, and launch the moving function.
        $scope.$watch('moveToClassroom', function (classroom) {
            if (!classroom) { return; }
            var msg = "Are you sure you want to move " +
                      $scope.selectedUsers.length + " students to " +
                      classroom.name + "?";
            if (confirm(msg)) {
                $scope.moveStudents($scope.selectedUsers, classroom);
            } else {
                $scope.moveToClassroom = undefined;
            }
        });

        // Re-associate students to another classroom.
        $scope.moveStudents = function (studentIds, newClassroom) {
            var moveSingleStudent = function (student_id) {
                // It is important to unassociate the student from the
                // classroom FIRST (before associating them to the new
                // one), because it also (like associate) cascades the
                // change through higher entities. Doing it second would
                // erase any higher associations that overlap with the new
                // association, like the cohort and program.

                // tl;dr: if you don't do it this way, you get a student
                // who has no program or cohort.

                return $pertsAjax({
                    url: '/api/unassociate/user/' + student_id +
                         '/classroom/' + $scope.classroom.id
                }).then(function (response) {
                    return $pertsAjax({
                        url: '/api/associate/user/' + student_id +
                             '/classroom/' + newClassroom.id
                    });
                });
            };

            $forEachAsync(studentIds, moveSingleStudent, 'serial').then(function () {
                $scope.selectedUsers = [];
                // remove those users from the list
                $scope.userList = forEach($scope.userList, function (u) {
                    if (!studentIds.contains(u.id)) {
                        return u;
                    }
                });
            });
        };
    };
    return {
        scope: {
            classroom: '=classroom',
            cohort: '=cohort',
            makeups: '@makeups'
        },
        controller: controller,
        link: function (scope, element, attrs) {
            // running sortBy sets scope.reverseSort and scope.sortedColumn
            var table = element.children('table.roster_table').get();
            scope.sortBy = sortByFactory(scope, table, 'tbody');
            scope.sortIconClass = sortIconClassFactory(scope);
        },
        templateUrl: '/static/dashboard_widgets/roster_table.html'
    };
});

PertsApp.directive('rosterRow', function () {
    'use strict';
    return {
        scope: {
            id: '@userId',
            filterText: '=filterText',
            sessions: '=sessions',
            classroom: '=classroom',
            makeups: '=makeups',
            makeupSession: '=makeupSession'
        },
        controller: function ($scope, $getStore, $seeStore, $pertsAjax, $location, $modal, $emptyPromise, $window) {
            // Status codes keyed by ordinal number.
            $scope.myCodes = {};
            $scope.mergeTargets = {};

            // Boot up the widget when the user's id is available.
            $scope.$watch('id', function (value) {
                $scope.user = $getStore.get($scope.id);
            });

            // Announce changes to the selected checkbox to the table.
            $scope.$watch('isSelected', function (isSelected) {
                $scope.$emit('/rosterRow/selectionChange', $scope.user.id,
                             isSelected);
            });

            // Synchronize status code details with the codes stored on the
            // user object. These details control things like dropping students
            // from the make-up list if they have a make-up ineligible code.
            $scope.$watch('user.status_codes', function (newList) {
                forEach(newList, function (activityOrdinal, code) {
                    $scope.myCodes[activityOrdinal] = $window.statusCodes[code];
                });
            }, true);  // watch for object value, not just reference

            // Load users who have been specified as merge targets so we can
            // display their names in the view.
            $scope.$watch('user.merge_ids', function (mergeIdObj) {
                if (!mergeIdObj) { return; }

                // Make one ajax transaction to get them all, then assign them
                // to their respective sessions one at a time.
                var mergeIds = forEach(mergeIdObj, function (sessionOrdinal, mergeId) {
                    return mergeId;
                });
                $getStore.load(mergeIds);

                forEach(mergeIdObj, function (sessionOrdinal, mergeId) {
                    var mergeTarget = $getStore.get(mergeId);
                    $scope.mergeTargets[sessionOrdinal] = $getStore.get(mergeId);
                });
            }, true);

            $scope.$on('/rosterTable/toggleSelectAll', function (event, checked) {
                $scope.isSelected = checked;
            });

            // Wrangle status codes into a nice format for drop-down menus.
            $scope.statusCodes = forEach($window.statusCodes, function (code, info) {
                var group;
                if (info.study_eligible) {
                    if (info.makeup_eligible) {
                        group = "Make-Up Eligible";
                    } else {
                        group = "Make-Up Ineligible";
                    }
                } else {
                    group = "Study Ineligible";
                }
                return {
                    id: code,
                    label: info.label,
                    group: group
                };
            });

            // Add a blank option so the drop down menu can be cleared.
            // Javascript null will translate to python None.
            $scope.statusCodes.unshift({id: null, label: ''});

            // Handy access to the seeStore in markup. Used to display
            // classroom names given their id.
            $scope.see = function (id) {
                return $seeStore.get(id);
            };

            // Translates certified true/false into display text for select.
            $scope.getCertifiedLabel = function (b) {
                return b ? 'Certified' : 'Uncertified';
            };

            $scope.progress = function (session) {
                if (!$scope.user._aggregation_data || !session) { return; }
                var d = $scope.user._aggregation_data[session.activity_ordinal] || {};
                return d.progress || '0';
            };

            // Clear user merge ids if they don't apply. Javascript null is
            // eventually translated to python None on the server.
            $scope.$watch('user', function (user) {
                forEach(user.merge_ids, function (sessionOrdinal, mergeId) {
                    var code = user.status_codes[sessionOrdinal];
                    if (mergeId && code !== 'MWN') {
                        user.merge_ids[sessionOrdinal] = null;
                    }
                });
            }, true);

            $scope.openDialog = function (activityOrdinal) {
                var parentScope = $scope;
                var controller = function ($scope, $modalInstance) {
                    $scope.close = function () {
                        $modalInstance.dismiss('close');
                    };
                };
                var dialogMarkup = '' +
                    '<div class="modal-header">' +
                        '<h3>Merge With</h3>' +
                    '</div>' +
                    '<div class="modal-body">' +
                        '<p>' +
                            'Merge student <strong>' + $scope.user.first_name +
                            ' ' + $scope.user.last_name + '</strong> with:' +
                        '</p>' +
                        '<p>' +
                            '<select chosen-select ' +
                                    'data-placeholder="merge with student..." ' +
                                    'select-options="mergeList" ' +
                                    'ng-options="u.id as (u.first_name + \' \' + u.last_name) for u in mergeList" ' +
                                    'ng-model="user.merge_ids[' + activityOrdinal + ']">' +
                            '</select>' +
                        '</p>' +
                    '</div>' +
                    '<div class="modal-footer">' +
                        '<button ng-click="close()">' +
                            'Close' +
                        '</button>' +
                    '</div>';

                // To display this dialog correctly, we need a list of all the
                // students in the cohort. Only load this when the dialog is
                // first opened b/c most of the time we won't need it.
                if ($scope.mergeList) {
                    var promise = $emptyPromise();
                } else {
                    var promise = $pertsAjax({
                        url: '/api/get/user',
                        params: {
                            user_type: 'student',
                            assc_cohort_list: $scope.$root.cohort.id
                        }
                    }).then(function (mergeList) {
                        // Take the user represented by this row out of the
                        // list, because it doesn't make any sense to merge
                        // a student with themselves.
                        mergeList = mergeList.filter(function (user) {
                            return user.id !== $scope.user.id;
                        })
                        $scope.mergeList = $getStore.setList(mergeList);
                    });
                }
                promise.then(function () {
                    var modalInstance = $modal.open({
                        backdrop: true,
                        keyboard: true,
                        backdropFade: true,
                        scope: $scope,
                        template:  dialogMarkup,
                        controller: controller
                    });
                });
            };
        },
        link: function (scope, element, attrs) {
            watchFilter(scope, element);
        },
        templateUrl: '/static/dashboard_widgets/roster_row.html'
    };
});


PertsApp.directive('userBasics', function () {
    'use strict';
    return {
        scope: {
            id: '@userId'
        },
        controller: function ($scope, $getStore, $pertsAjax) {
            $scope.$watch('id', function (value) {
                $scope.user = $getStore.get(value);
            });
            $scope.syncNames = function () {
                if (!$scope.user.name) {
                    $scope.user.name = $scope.user.first_name;
                }
            };
            $scope.deleteUser = function (user) {
                if (confirm("Are you sure you want to delete " + user.login_email + "?")) {
                    var url = '/api/delete/user/' + user.id;
                    $pertsAjax({url: url}).then(function () {
                        window.location.reload();
                    });
                }
            };
        },
        templateUrl: '/static/dashboard_widgets/user_basics.html'
    };
});

PertsApp.directive('changePassword', function () {
    'use strict';
    return {
        scope: {
            id: '@userId'
        },
        controller: function ($scope, $getStore, $pertsAjax) {
            $scope.newPasswordBlurred = false;
            $scope.repeatPasswordBlurred = false;
            $scope.success = null;
            // At least 8 characters, ascii only.
            // http://stackoverflow.com/questions/5185326/java-script-regular-expression-for-detecting-non-ascii-characters.
            $scope.passwordRegex = /^[\040-\176]{8,}$/;
            $scope.$watch('id', function (value) {
                $scope.user = $getStore.get(value);
            });
            $scope.isMe = function () {
                return window.userId === $scope.id;
            };
            $scope.passwordsMatch = function () {
                if (!$scope.newPassword || !$scope.repeatPassword) {
                    return false;
                } else {
                    return $scope.newPassword === $scope.repeatPassword;
                }
            };
            $scope.changePassword = function () {
                $scope.success = null;
                $pertsAjax({
                    url: '/api/change_password',
                    method: 'POST',
                    params: {
                        username: $scope.user.login_email,
                        current_password: $scope.currentPassword,
                        new_password: $scope.newPassword
                    }
                }).then(function (response) {
                    if (response === 'changed') {
                        $scope.success = true;
                        $scope.successMessage = "Password changed.";
                        $scope.currentPassword = '';
                        $scope.newPassword = '';
                        $scope.repeatPassword = '';
                        $scope.newPasswordBlurred = false;
                        $scope.repeatPasswordBlurred = false;
                    } else if (response === 'invalid_credentials') {
                        $scope.success = false;
                        $scope.successMessage = "Incorrect password. Password has not been changed.";
                    }
                });
            };
        },
        templateUrl: '/static/dashboard_widgets/change_password.html'
    };
});

PertsApp.directive('userEntryList', function () {
    'use strict';
    var controller = function ($scope, $seeStore, $getStore, $pertsAjax, $forEachAsync, $modal, $window) {
        $scope.selectedUsers = [];

        $scope.columns = [
            {name: "", colClass: 'select', sortable: false},
            {name: "First", colClass: 'first_name', sortable: true},
            {name: "Last", colClass: 'last_name', sortable: true},
            {name: "Phone #", colClass: 'phone', sortable: true},
            {name: "Date Registered", colClass: 'registered', sortable: true},
            {name: "Oversees Schools", colClass: 'owned_schools', sortable: false},
            {name: "Verified?", colClass: 'verified', sortable: true}
        ];

        var params = {user_type_json: ['school_admin', 'teacher']};
        if ($scope.$root.level === 'program') {
            // filter by given program
            params.assc_program_list = $scope.$root.entityId;
        } else if ($scope.$root.level === 'cohort') {
            // filter by given cohort, but use 'owned' list b/c
            // that's how school admins are related.
            params.owned_cohort_list = $scope.$root.entityId;
        }

        // Query for relevant users.
        $pertsAjax({
            url: '/api/get/user',
            params: params
        }).then(function (response) {
            $scope.userList = $getStore.setList(response);
        });

        // Get the names of all the owned cohorts so we can display them.
        // We need them for both the owned-school tags in each row, and
        // for the association drop-down.
        var programId;
        if ($scope.$root.level === 'program') {
            programId = $scope.$root.currentEntity.id;
        } else {
            programId = $scope.$root.currentEntity.assc_program_list[0];
        }
        $pertsAjax({
            url: '/api/see/cohort',
            params: {assc_program_list: programId}
        }).then(function (response) {
            $scope.availableCohorts = $seeStore.setList(response);
        });

        $scope.$watch('newAdminCohort', function (cohort) {
            if (!cohort) { return; }
            // A cohort has been selected from the association dropdown.
            // Make the selected users owners of this cohort.
            $scope.$broadcast('/userEntryList/setOwner', cohort.id,
                         $scope.selectedUsers);

            // Clear the select box so it can be used again.
            $scope.newAdminCohort = undefined;
            // Notify the chosen plugin of the change after the current digest
            // has finished.
            setTimeout(function () {
                $('[chosen-select]').trigger('chosen:updated');
            }, 1);
        });

        $scope.deleteSelectedUsers = function () {
            // Make sure they didn't click by mistake.
            var msg = "Are you sure you want to delete " +
                $scope.selectedUsers.length + " users?";
            if (!confirm(msg)) { return; }

            // Delete each user one by one.
            $forEachAsync($scope.selectedUsers, function (userId) {
                return $pertsAjax({url: '/api/delete/user/' + userId});
            }, 'serial').then(function () {
                // Rebuild the list of displayed users based on which
                // ones weren't just deleted.
                $scope.userList = forEach($scope.userList, function (user) {
                    if (!$scope.selectedUsers.contains(user.id)) {
                        return user;
                    }
                });
                // Uncheck all the select boxes.
                $scope.selectedUsers = [];
            });
        };

        $scope.trackSelection = function (event, userId, isSelected) {
            if (
                isSelected === true &&
                !$scope.selectedUsers.contains(userId)
            ) {
                $scope.selectedUsers.push(userId);
            } else if (isSelected === false) {
                $scope.selectedUsers.remove(userId);
            }
        };

        $scope.toggleSelectAll = function (checked) {
            $scope.$broadcast('/userEntryList/toggleSelectAll', checked);
        };

        // Listen to rows whose checkboxes change and track them.
        $scope.$on('/userEntry/selectionChange', $scope.trackSelection);

        // Build a dialog box for displaying email addresses of selected users.
        $scope.openDialog = function () {
            var testingDialogMarkup = '' +
                '<div class="modal-header">' +
                    '<h3>Email Addresses: paste into "To:" field</h3>' +
                '</div>' +
                '<div class="modal-body">' +
                    '<p>' +
                        forEach($scope.userList, function (u) {
                            if ($scope.selectedUsers.contains(u.id)) {
                                return u.login_email;
                            }
                        }).join(', ') +
                    '</p>' +
                '</div>' +
                '<div class="modal-footer">' +
                    '<button ng-click="close()" class="btn btn-default">' +
                        'Close' +
                    '</button>' +
                '</div>';
            // See angular-ui docs for details on available options.
            // http://angular-ui.github.io/bootstrap/#/modal
            var modalInstance = $modal.open({
                backdrop: true,
                keyboard: true,
                backdropClick: true,
                backdropFade: true,
                template:  testingDialogMarkup,
                controller: function ($scope, $modalInstance) {
                    $scope.close = function () {
                        $modalInstance.dismiss('close');
                    };
                }
            });
        };

    };
    return {
        scope: {},
        controller: controller,
        link: function (scope, element, attrs) {
            // running sortBy sets scope.reverseSort and scope.sortedColumn
            var table = element.children('table').get();
            scope.sortBy = sortByFactory(scope, table, 'tr');
            scope.sortIconClass = sortIconClassFactory(scope);
        },
        templateUrl: '/static/dashboard_widgets/user_entry_list.html'
    };
});

PertsApp.directive('userEntry', function () {
    'use strict';
    var controller = function ($scope, $pertsAjax, $seeStore, $getStore, $window) {
        $scope.$watch('userId', function (userId) {
            if (!userId) { return; }
            $scope.user = $getStore.get(userId);

            if ($scope.user.created) {
                $scope.registered = Date.createFromString($scope.user.created, 'UTC')
                    .toLocaleDateString();
            }

            $scope.processRelationships();
        }, true);

        $scope.$watch('user.user_type', function (userType) {
            if (userType === 'teacher') {
                $scope.verifiedString = "No";
                $scope.verifiedTooltip = "To verify this administrator, " +
                    "make them the owner of a school.";
            } else {
                $scope.verifiedString = "Yes";
                $scope.verifiedTooltip = "";
            }
        });

        // Announce changes to the selected checkbox to the table.
        $scope.$watch('isSelected', function (isSelected) {
            $scope.$emit('/userEntry/selectionChange', $scope.user.id,
                         isSelected);
        });

        $scope.$on('/userEntryList/toggleSelectAll', function (event, checked) {
            $scope.isSelected = checked;
        });

        $scope.$on('/userEntryList/setOwner', function (event, cohortId, selectedUsers) {
            // Don't execute if this broadcast doesn't apply to us.
            if (!selectedUsers.contains($scope.user.id)) { return; }
            $scope.makeSchoolAdmin(cohortId);
        });

        $scope.processRelationships = function () {
            if (!$scope.user.owned_cohort_list) { return; }
            $scope.ownedCohorts = $seeStore.getList($scope.user.owned_cohort_list);
        };

        $scope.makeSchoolAdmin = function (cohortId) {
            // 1) Make this user a school admin
            // 2) Make them the owner of the specified cohort
            $pertsAjax({
                url: '/api/set_owner/user/' + $scope.user.id +
                     '/cohort/' + cohortId
            }).then(function (user) {
                // Update local data model with new user associations.
                $scope.user = $getStore.set(user);
                $scope.processRelationships();
                // $getStore will save this to the server for us.
                $scope.user.user_type = 'school_admin';
            });
        };

        $scope.disownCohort = function (cohortId) {
            return $pertsAjax({
                url: '/api/disown/user/' + $scope.user.id +
                     '/cohort/' + cohortId
            }).then(function (user) {
                $getStore.set(user);
                $scope.processRelationships();
            });
        };
    };
    return {
        scope: {
            userId: '@userId',
            filterText: '='
        },
        controller: controller,
        link: function (scope, element, attrs) {
            watchFilter(scope, element);
        },
        templateUrl: '/static/dashboard_widgets/user_entry.html'
    };
});


// Helps scheduling widgets communicate with each other. Each widget records
// its date with the service. Widgets can also set up callbacks which are
// executed when an activity with the given user type and ordinal changes its
// date. Since multiple activities might meet this description, the latest one
// is provided to the callback.
PertsApp.factory('$scheduleRules', function () {
    'use strict';
    return {
        _d: {},
        _callbacks: {},
        init: function (classroomId, userType, ordinal) {
            forEach([['_d', {}], ['_callbacks', []]], function (i) {
                var p = i[0], v = i[1],
                    blankClassroom = {teacher: {}, student: {}};
                util.initProp(this[p], classroomId, blankClassroom);
                util.initProp(this[p][classroomId][userType], ordinal, v);
            }, this);
        },
        addDate: function (activity, date) {
            // record the date
            var classroomId = activity.assc_classroom_list[0];
            var userType = activity.user_type;
            var ordinal = activity.activity_ordinal;

            this.init(classroomId, userType, ordinal);

            var dates = this._d[classroomId][userType][ordinal];
            dates[activity.id] = date;

            // find the latest date from this set
            var latestDate;
            forEach(dates, function (activityId, date) {
                if (latestDate === undefined) {
                    latestDate = date;
                } else if (date > latestDate) {
                    latestDate = date;
                }
            });

            // call the appropriate callbacks
            var callbacks = this._callbacks[classroomId][userType][ordinal];
            forEach(callbacks, function (f) {
                f(latestDate);
            });
        },
        watch: function (classroomId, relativeInfo, callback) {
            var userType = relativeInfo[0];
            var ordinal = relativeInfo[1];

            this.init(classroomId, userType, ordinal);

            this._callbacks[classroomId][userType][ordinal].push(callback);
        }
    };
});

// Will query the server and build appropriate user entry widgets based on
// response.
PertsApp.config(function ($routeProvider) {
    'use strict';
    $routeProvider.when('/:level/:entityId/:page', {
            controller: DashboardController,
            templateUrl: '/static/dashboard_pages/base.html'
        }).otherwise({
            controller: DashboardController,
            templateUrl: '/static/dashboard_pages/base.html'
        });
}).run(function ($seeStore, $getStore) {
    'use strict';
    // Runs every second, sends /api/put calls for updated entities.
    $getStore.watchForUpdates();
    $seeStore.watchForUpdates();
});
