/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License 
*/
import 'dart:math';
import 'package:flutter/material.dart';

class GaugePainter extends CustomPainter {
  final double currentValue;
  final double minValue;
  final double maxValue;
  final List<Color> segmentColors;
  final double majorTickStep;
  final double medianTickStep;
  final double minorTickStep;
  final double sweepAngle;
  final bool showSegmentValues;
  final bool showMajorTickValues;
  final bool showMedianTickValues;
  final int numberOfSegments;
  final double strokeWidth;
  final String? valueText;

  GaugePainter({
    required this.currentValue,
    this.valueText,
    required this.minValue,
    required this.maxValue,
    required this.segmentColors,
    required this.majorTickStep,
    this.medianTickStep = 0,
    required this.minorTickStep,
    required this.sweepAngle,
    this.showSegmentValues = true,
    this.showMajorTickValues = false,
    this.showMedianTickValues = false,
    this.strokeWidth = 20.0,
  }) : numberOfSegments = segmentColors.length;

  @override
  void paint(Canvas canvas, Size size) {
    final Offset center = Offset(size.width / 2, size.height / 2 + 25);
    final double radius = size.width / 2;
    final double segmentAngle = sweepAngle / numberOfSegments;

    // Draw three segments with different colors
    for (int i = 0; i < numberOfSegments; i++) {
      final startAngle = -90 - sweepAngle / 2 + segmentAngle * i;
      final paint = Paint()
        ..color = segmentColors[i]
        ..style = PaintingStyle.stroke
        ..strokeWidth = strokeWidth;

      canvas.drawArc(Rect.fromCircle(center: center, radius: radius),
          degToRad(startAngle), degToRad(segmentAngle), false, paint);
    }
    // Draw the ticks
    drawTicks(canvas, center, radius); //, true);
    // drawTicks(canvas, center, radius); //, false);

    // Draw the needle
    final needlePaint = Paint()
      ..color = Colors.black
      ..style = PaintingStyle.fill;

    final percent = (currentValue - minValue) / (maxValue - minValue);
    final needleAngle = -90 - sweepAngle / 2 + sweepAngle * percent;
    final needleLength = radius - 20;

    final path = Path();
    path.moveTo(center.dx + 3, center.dy);
    path.lineTo(center.dx - 3, center.dy);
    path.lineTo(center.dx + needleLength * cos(degToRad(needleAngle - 1)),
        center.dy + needleLength * sin(degToRad(needleAngle - 1)));
    path.lineTo(center.dx + needleLength * cos(degToRad(needleAngle + 1)),
        center.dy + needleLength * sin(degToRad(needleAngle + 1)));
    path.lineTo(center.dx + 3, center.dy);
    path.close();

    canvas.drawPath(path, needlePaint);

    // Draw the value
    final textPainter = TextPainter(
      text: TextSpan(
        text: currentValue.toStringAsFixed(2),
        style: const TextStyle(
            color: Colors.black, fontSize: 14.0, fontWeight: FontWeight.bold),
      ),
      textDirection: TextDirection.ltr,
    );
    textPainter.layout();
    textPainter.paint(
        canvas,
        Offset(center.dx - textPainter.width / 2,
            center.dy - textPainter.height + 25 / 3 * 2));
    // Draw the label
    if (valueText != null) {
      final textPainterLbl = TextPainter(
        text: TextSpan(
          text: valueText ?? '',
          style: const TextStyle(
              color: Colors.black,
              fontSize: 10.0,
              fontWeight: FontWeight.normal),
        ),
        textDirection: TextDirection.ltr,
      );
      textPainterLbl.layout();
      textPainterLbl.paint(
          canvas,
          Offset(
              center.dx - textPainterLbl.width / 2,
              center.dy +
                  textPainter.height -
                  textPainterLbl.height +
                  25 / 3 * 2));
    }
  }

  double degToRad(double deg) => deg * pi / 180;

  double getRadAngleForValue(double value) {
    return degToRad(-90 -
        sweepAngle / 2 +
        sweepAngle * ((value - minValue) / (maxValue - minValue)));
  }

  double getDegreesAngleForValue(double value) {
    return -90 -
        sweepAngle / 2 +
        sweepAngle * ((value - minValue) / (maxValue - minValue));
  }

  void drawTicks(Canvas canvas, Offset center, double radius) {
    if (majorTickStep == 0 && medianTickStep == 0 && minorTickStep == 0) return;
    final majorTickPaint = Paint()
      ..color = Colors.black
      ..strokeWidth = 1.5;

    // style for minor AND median
    final minorTickPaint = Paint()
      ..color = Colors.black
      ..strokeWidth = 0.5;

    for (double thickValue = minValue;
        thickValue <= maxValue;
        thickValue += minorTickStep) {
      final double thickAngle = getDegreesAngleForValue(thickValue);

      final double startRadius =
          (majorTickStep > 0 && (thickValue % majorTickStep == 0))
              ? radius - strokeWidth / 2
              : (medianTickStep > 0 && (thickValue % medianTickStep == 0))
                  ? radius - strokeWidth / 2
                  : radius - strokeWidth / 2;
      final Offset startTick = Offset(
        center.dx + startRadius * cos(thickAngle * pi / 180),
        center.dy + startRadius * sin(thickAngle * pi / 180),
      );
      final double endRadius =
          (majorTickStep > 0 && (thickValue % majorTickStep == 0))
              ? radius + strokeWidth / 2 * 0.7
              : (medianTickStep > 0 && (thickValue % medianTickStep == 0))
                  ? radius + strokeWidth / 2 * 0.4
                  : radius;
      final Offset endTick = Offset(
        center.dx + endRadius * cos(thickAngle * pi / 180),
        center.dy + endRadius * sin(thickAngle * pi / 180),
      );
      canvas.drawLine(
        startTick,
        endTick,
        (majorTickStep > 0 && (thickValue % majorTickStep == 0))
            ? majorTickPaint
            : minorTickPaint,
      );
    }

    // Add values at the beginning of each segment
    final textPainter = TextPainter(
      textDirection: TextDirection.ltr,
    );

    final double segmentValueStep =
        (maxValue - minValue) / segmentColors.length;

    for (int i = 0; i <= segmentColors.length; i++) {
      final double value = minValue + segmentValueStep * i;
      // final double angleInDegrees =
      //     sweepAngle * (value - minValue) / (maxValue - minValue);

      textPainter.text = TextSpan(
        text: value.toStringAsFixed(0),
        style: const TextStyle(
          color: Colors.black,
          fontSize: 10.0,
        ),
      );

      textPainter.layout();

      final Offset textOffset = Offset(
        center.dx +
            (radius - 20) * cos(getRadAngleForValue(value)) -
            textPainter.width / 2,
        center.dy +
            (radius - 20) * sin(getRadAngleForValue(value)) -
            textPainter.height / 2,
      );

      textPainter.paint(canvas, textOffset);
    }
  }

  @override
  bool shouldRepaint(CustomPainter oldDelegate) => true;
}

class Gauge extends StatelessWidget {
  final Size widgetSize;
  final double currentValue;
  final String? valueText;
  final double minValue;
  final double maxValue;
  final List<Color> segmentColors;
  final double majorTickStep;
  final double medianTickStep;
  final double minorTickStep;
  final double sweepAngle;
  final bool showSegmentValues;
  final bool showMajorTickValues;
  final bool showMedianTickValues;
  final double strokeWidth;

  const Gauge(
    this.currentValue,
    this.valueText, {
    Key? key,
    required this.minValue,
    required this.maxValue,
    required this.segmentColors,
    required this.majorTickStep,
    this.medianTickStep = 0,
    required this.minorTickStep,
    required this.sweepAngle,
    this.showSegmentValues = true,
    this.showMajorTickValues = false,
    this.showMedianTickValues = false,
    this.widgetSize = const Size(200, 140),
    this.strokeWidth = 20.0,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      size: widgetSize,
      painter: GaugePainter(
          currentValue: currentValue,
          valueText: valueText,
          minValue: minValue,
          maxValue: maxValue,
          segmentColors: segmentColors,
          majorTickStep: majorTickStep,
          medianTickStep: medianTickStep,
          minorTickStep: minorTickStep,
          sweepAngle: sweepAngle,
          showSegmentValues: showSegmentValues,
          showMajorTickValues: showMajorTickValues,
          showMedianTickValues: showMajorTickValues),
    );
  }
}

/*

class GaugePainter extends CustomPainter {
  final double minValue;
  final double maxValue;
  final double currentValue;
  late double percentage;

  GaugePainter(this.currentValue,
      {required this.minValue, required this.maxValue}) {
    percentage = (currentValue - minValue) / (maxValue - minValue);
  }

  @override
  void paint(Canvas canvas, Size size) {
    final startAngle = -pi;
    final sweepAngle = 2 * pi * percentage;

    // Draw the track.
    final trackPaint = Paint()
      ..color = Colors.grey[300]!
      ..strokeWidth = 10.0
      ..style = PaintingStyle.stroke;
    canvas.drawCircle(
      size.center(Offset.zero),
      size.width / 2,
      trackPaint,
    );

    // Draw the bar.
    final barPaint = Paint()
      ..strokeWidth = 10.0
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..shader = const SweepGradient(
        colors: [Colors.blue, Colors.green, Colors.red],
        stops: [0.0, 0.5, 1.0],
      ).createShader(
        Rect.fromCircle(
          center: size.center(Offset.zero),
          radius: size.width / 2,
        ),
      );
    canvas.drawArc(
      Rect.fromCenter(
        center: size.center(Offset.zero),
        width: size.width,
        height: size.height,
      ),
      startAngle,
      sweepAngle,
      false,
      barPaint,
    );

    // Draw the text.
    final textPainter = TextPainter(
      text: TextSpan(
        text: '${(currentValue).toStringAsFixed(0)}',
        style: TextStyle(
          color: Colors.black,
          fontSize: size.width / 4,
        ),
      ),
      textDirection: TextDirection.ltr,
    );
    textPainter.layout();
    textPainter.paint(
      canvas,
      size.center(Offset.zero) -
          Offset(textPainter.width / 2, textPainter.height / 2),
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => true;
}

class GaugeChart extends StatelessWidget {
  final double minValue;
  final double maxValue;
  final double currentValue;

  GaugeChart(this.currentValue,
      {required this.minValue, required this.maxValue});

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      painter:
          GaugePainter(currentValue, maxValue: maxValue, minValue: minValue),
      child: Container(),
    );
  }
}
*/