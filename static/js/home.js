/** Javscript file for PERTS homepage(s)
  * Created: 4/1/15
  **/

'use strict';

var pertsApp = angular.module('pertsApp', []);

pertsApp.config(['$interpolateProvider', function ($interpolateProvider) {
  // Change the default bracket notation, which is normally {{ foo }},
  // so that it doesn't interfere with jinja (server-side templates).
  // That means angular interpolation is done like this: {[ foo ]}.
  $interpolateProvider.startSymbol('{[');
  $interpolateProvider.endSymbol(']}');
}]);

pertsApp.run(['$window', '$rootScope', '$interval', function ($window, $rootScope, $interval) {

  FastClick.attach(document.body);

  // Smooth scrolling for hash anchor tags
  $('a[href*=#]').on('click', function() {
    var containerPos = $('.full-container').scrollTop() || 0;
    var navbarHeight = $('nav.navbar').outerHeight() || 0;
    var targetOffset = $( $.attr(this, 'href') ).offset();

    if (targetOffset) {
      var pos = containerPos - navbarHeight + targetOffset.top;
      $('html, body').animate({scrollTop: pos}, 400);
    } // Else target can't be found; do nothing.
  });

  // Navbar toggle
  $('a#navToggle').on('click', function (e) {
    $('.navbar_links').toggleClass('active');
    $('.toggle-icon').toggleClass('active');
    e.preventDefault();
  });

  var pageHeight = $(window).height();
  var navOpened = false;
  var navTrigger = 150; // Minimum distance down page to trigger navbar

  // Pixels moved up or down before hiding/showing nav.
  var accelTrigger = 50; // Distance in one direction to open or close
  var accelDown = true;
  var accelPoint = 150;
  var lastPoint = $(this).scrollTop();

  $(window).scroll(function () {

    // // Hides nav if above the fold.
    // if (navOpened && ($(this).scrollTop()) <= navTrigger) {
    //   $('nav.navbar').removeClass('active');
    //   navOpened = false;
    // }

    // // Reset point on accel direction change
    // if (accelDown !== (lastPoint < $(this).scrollTop())) {
    //   accelDown = lastPoint < $(this).scrollTop();
    //   accelPoint = $(this).scrollTop();
    // }

    // if ($(this).scrollTop() > navTrigger) {
    //   // Below fold, do accelerated calculation.
    //   if (!accelDown && !navOpened) {
    //     // CASE: Moving up
    //     if ($(this).scrollTop() < (accelPoint - accelTrigger)) {
    //       $('nav.navbar').addClass('active');
    //       navOpened = true;
    //     }
    //   } else if (navOpened) {
    //     // CASE: Moving down
    //     if ($(this).scrollTop() > (accelPoint + accelTrigger)) {
    //       $('nav.navbar').removeClass('active');
    //       navOpened = false;
    //     }
    //   }
    // }
    // lastPoint = $(this).scrollTop();

    // Simple navbar controller as you scroll down
    // Opens after 'navtrigger' and closes above
    if (!navOpened && ($(this).scrollTop() > navTrigger)) {
      $('nav.navbar').addClass('active');
      navOpened = true;
    } else if (navOpened && ($(this).scrollTop() <= navTrigger)) {
      $('nav.navbar').removeClass('active');
      navOpened = false;
    }

  });

  $rootScope.navOpen = false;

  $rootScope.toggleNav = function() {
    $rootScope.navOpen = !$rootScope.navOpen;
  };

  $rootScope.currentCard = 1;
  $rootScope.pauseCarousel = false;

  $rootScope.incrementCard = function () {
    if ($rootScope.currentCard === 3) {
      $rootScope.currentCard = 1;
    } else {
      $rootScope.currentCard += 1;
    }
  };

  // Wrapper function to turn off auto-increment on click
  $rootScope.setCarouselCard = function (number) {
    $rootScope.pauseCarousel = true;
    $rootScope.currentCard = number;
  };

  $interval( function () {
    if (!$rootScope.pauseCarousel) {
      $rootScope.incrementCard();
    }
  }, 4500);

}]);

// Contact controller

pertsApp.controller('ContactCtrl', ['$scope', '$http', function ($scope, $http) {

  $scope.submitContact = function() {

    if (!$scope.sending) {
      $scope.sending = true;
      $scope.messageError = false;
      $http.post('/api/send_contact_email', $scope.contact)
        .then(function (data) {
          $scope.messageSent = true;
          $scope.sending = false;
        }).catch(function (error) {
          $scope.messageError = true;
          $scope.sending = false;
        });
    }
  };

}]);

// Image loader

pertsApp.directive('imageLoader', ['$window', '$timeout', function ($window, $timeout) {

  function getWidth() {
    if (self.innerHeight) {
      return self.innerWidth;
    }

    if (document.documentElement && document.documentElement.clientHeight) {
      return document.documentElement.clientWidth;
    }

    if (document.body) {
      return document.body.clientWidth;
    }
  }

  return {
    template: '',
    restrict: 'A',
    scope: true,
    link: function (scope, element, attrs) {

      var imageUrl;

      var img = new Image();
      img.onload = function() {
        element.removeClass('loading');

        $timeout(function(){
          element.addClass('loaded');
        }, 100);
      };

      if (attrs.mobile && getWidth() <= 767) {
        imageUrl = attrs.mobile;
      } else {
        imageUrl = attrs.image;
      }

      img.src = imageUrl;

      element.css('background-image', 'url(' + imageUrl + ')');
      // element.css('background-size', 'cover');
      // element.css('background-position', 'center center');

      scope.$watch( function() { return attrs.image; }, function() {
        if (attrs.image) {

          var oldImage = imageUrl;

          if (attrs.mobile && getWidth() <= 767) {
            imageUrl = attrs.mobile;
          } else {
            imageUrl = attrs.image;
          }

          // Prevents re-animating the same image
          if (oldImage === imageUrl) {
            return;
          }

          element.removeClass('loaded');
          element.addClass('loading');

          $timeout(function(){
            img.src = imageUrl;
            element.css('background-image', 'url(' + imageUrl + ')');
          }, 200);

        }

      });

    }
  };
}]);