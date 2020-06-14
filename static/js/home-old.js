/** Javscript file for PERTS homepage(s)
  * Created: 4/1/15
  **/

'use strict';

var Perts = {};

// Colors used for drawing charts

Perts.colors = {
  blueColor: '#135691',
  darkBlueColor: '#042744',
  violetColor: '#8384F7',
  accentColor: '#C44606',
  lightBlueColor: '#69a7d3'
};

Perts.quoteNumber = 1;

$( function () {

  'use strict';

  // Prevents tap delay on mobile
  FastClick.attach(document.body);

  if (window.location.pathname === '/') {

    var width = $(".d3-graphic-holder").width() || 960,
        height = $(".d3-graphic-holder").height() || 500;

    var d3_geom_voronoi = d3.geom.voronoi().x(function(d) { return d.x; }).y(function(d) { return d.y; })

    var nodes = d3.range(240).map(function(i) {
      return {index: i};
    });

    var force = d3.layout.force()
      .nodes(nodes)
      .size([width, height])
      .charge(-320)
      .start();

    var container = d3.select(".d3-graphic-holder");
    var svg = container.append("svg")
        .attr("width", container.width)
        .attr("height", container.height);

    var node = svg.selectAll(".node")
        .data(nodes)
      .enter().append("circle")
        .attr("class", "node")
        .attr("cx", function(d) { return d.x; })
        .attr("cy", function(d) { return d.y; })
        .attr("r", 4)
        .call(force.drag)

    svg.style("opacity", 1e-6)
      .transition()
        .duration(1000)
        .style("opacity", 1);

    var link = svg.selectAll("line");

    force.on("tick", function() {
      node.attr("cx", function(d) { return d.x; })
          .attr("cy", function(d) { return d.y; });

      link = link.data(d3_geom_voronoi.links(nodes))
      link.enter().append("line")
      link.attr("x1", function(d) { return d.source.x; })
          .attr("y1", function(d) { return d.source.y; })
          .attr("x2", function(d) { return d.target.x; })
          .attr("y2", function(d) { return d.target.y; })

      link.exit().remove();

    });


    var pageHeight = $(window).height();
    var navOpened = false;
    var chartsTriggered = false;
    var quotesTriggered = false;
    var partnersTriggered = false;
    var involvedTriggered = false;
    var incrementingPaused = false;

    $(window).scroll(function () {

      // Animations in introduction section

      if (!navOpened && ($('#navTrigger').offset().top - $(this).scrollTop()) < 0) {
        $('nav.small-navbar').addClass('active');
        navOpened = true;
      }

      if (navOpened && ($('#navTrigger').offset().top - $(this).scrollTop()) > 0) {
        $('nav.small-navbar').removeClass('active');
        navOpened = false;
      }

      if (($('#chartsCanvas').offset().top - $(this).scrollTop()) < pageHeight/1.4 && !chartsTriggered) {
        chartsTriggered = true;
        Perts.drawAllCharts();
      }

      if (($('#quoteBox').offset().top - $(this).scrollTop()) < pageHeight/1.4 && !quotesTriggered) {
        quotesTriggered = true;
        $('#quoteBox').addClass('active');
      }

      if (($('#partnersSection').offset().top - $(this).scrollTop()) < pageHeight/1.2 && !partnersTriggered) {
        partnersTriggered = true;
        $('.partner').addClass('active');
      }

      if (($('#involvedGraphic').offset().top- $(this).scrollTop()) < pageHeight/1.4 && !involvedTriggered) {
        involvedTriggered = true;
        $('#circle6').addClass('active');
        setTimeout( function () {
          $('#circle1').addClass('active');
          $('#circle2').addClass('active');
          $('#circle3').addClass('active');
          $('#circle4').addClass('active');
          $('#circle5').addClass('active');
        }, 500);
      }

    });

    $('li[data-quote-number]').on('click', function () {
      if (!($(this).hasClass('active'))) {
        Perts.setQuote($(this).data('quote-number'));
        incrementingPaused = true;
        setTimeout( function () {
          incrementingPaused = false;
        }, 10000);
      }
    });

    window.setInterval( function () {
      if (!incrementingPaused) {
        Perts.incrementQuoteNumber();
      }
    }, 6200);

  } else {

    // Functions for static pages

    $('#moreArticles').on('click', function () {
      $(this).hide();
      $('.past-articles').addClass('active');
    });

  }

  $('a[href*=#]').on('click', function() {
    $('html, body').animate({
      scrollTop: $( $.attr(this, 'href') ).offset().top - 60
    }, 400);
    return false;
  });

});

// Set quote number

Perts.setQuote = function (quoteNumber) {
  $('.quote-box').removeClass('active');
  $('.quote-box[data-number=' + quoteNumber + ']').addClass('active');
  $('li[data-quote-number]').removeClass('active');
  $('li[data-quote-number=' + quoteNumber + ']').addClass('active');
  Perts.quoteNumber = quoteNumber;
}

Perts.incrementQuoteNumber = function () {
  var newNumber = Perts.quoteNumber + 1;
  if (newNumber === 5) {
    newNumber = 1;
  }
  Perts.setQuote(newNumber);
}

// Function to find and draw all Charts

Perts.drawAllCharts = function () {
  // loop through all canvases with 'chart-type' attribute
  $("canvas[chart-type]").each(function (index, element) {
    if ($(element).attr('chart-type') === 'pie') {
      Perts.drawPieChart(element);
    } else if ($(element).attr('chart-type') === 'bar') {
      Perts.drawBarChart(element);
    }
  });
};

// Function to draw Pie Chart on canvas element

Perts.drawPieChart = function(chart) {
  var data = [30, 35, 45];
  // format data for Chart.js
  var formattedData = [
    {
      value: data[0],
      color: Perts.colors.lightBlueColor
    },{
      value: data[1],
      color: Perts.colors.darkBlueColor
    },{
      value: data[2],
      color: Perts.colors.blueColor
    }
  ];
  var options = {
    showTooltips: false
  };
  var ctx = chart.getContext('2d');
  // create chart using Chart.js
  var newChart = new Chart(ctx).Pie(formattedData, options);
  // remove added height and width to keep chart responsive
  // chart.removeAttribute('style');

};

// Function to draw Bar Graph on canvas element

Perts.drawBarChart = function(chart) {
  var data = [45, 57, 75];
  // format data for Chart.js
  var formattedData = {
    labels: [''],
    datasets: [{
        fillColor: Perts.colors.blueColor,
        strokeColor: Perts.colors.blueColor,
        data: [data[0]]
      },{
        fillColor: Perts.colors.lightBlueColor,
        strokeColor: Perts.colors.lightBlueColor,
        data: [data[1]]
      },{
        fillColor: Perts.colors.darkBlueColor,
        strokeColor: Perts.colors.darkBlueColor,
        data: [data[2]]
      }]
  };
  // set options for Chart.js
  var options = {
    // showScale: false,
    scaleShowLabels: false,
    showTooltips: false,
    scaleShowHorizontalLines: false,
    barDatasetSpacing : 14
  };
  var ctx = chart.getContext('2d');
  // create chart using Chart.js
  var newChart = new Chart(ctx).Bar(formattedData, options);
  // remove added height and width to keep chart responsive
  // chart.removeAttribute('style');
};