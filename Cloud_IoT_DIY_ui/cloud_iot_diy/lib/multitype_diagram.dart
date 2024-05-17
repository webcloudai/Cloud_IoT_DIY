/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License 
*/
import 'package:flutter/material.dart';
import 'package:graphic/graphic.dart' as graphic;
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:flutter/gestures.dart';
import 'gauge.dart';

enum ChartType { line, bar, gauge }

class ChartTypeConfig {
  static Map<ChartType, Map<String, String>> byType = {
    ChartType.line: {},
    ChartType.bar: {},
    ChartType.gauge: {
      "minValue": "10",
      "maxValue": "40",
      "sweepAngle": "200",
      "majorTickStep": "10",
      "medianTickStep": "5",
      "minorTickStep": "1",
    }
  };
}

class ChartData {
  ChartData(this.label, this.value) {
    try {
      label = DateTime.fromMicrosecondsSinceEpoch(int.parse(label) * 1000)
          .toString();
    } catch (e) {
      //label = "";
    }
  }
  String label;
  final num value;
}

class ChartWidget extends StatefulWidget {
  final String apiUrl;
  final ChartType chartType;
  final String accessToken;
  final Map<String, String>? diagramConfig;

  const ChartWidget(
      {Key? key,
      required this.apiUrl,
      required this.accessToken,
      required this.chartType,
      this.diagramConfig})
      : super(key: key);

  @override
  ChartWidgetState createState() => ChartWidgetState();
}

class ChartWidgetState extends State<ChartWidget> {
  List<ChartData> chartData = [];

  Future<List<ChartData>> fetchData(bool forceRefresh) async {
    if (chartData.isNotEmpty && !forceRefresh) return chartData;
    http.Response? response;
    chartData = [];
    try {
      response = await http.get(
        Uri.parse(widget.apiUrl),
        headers: {"Authorization": "Bearer ${widget.accessToken}"},
      );

      if (response.statusCode == 200) {
        // && response.body != null) {
        try {
          final List<dynamic> data = json.decode(response.body);
          setState(() {
            chartData = _convertDataToChartData(data);
          });
        } catch (e) {
          print("Exception when fetching data");
          print(e.toString());
          response = null;
        }
      } else {
        throw Exception('Failed to load data');
      }
    } catch (e) {
      print(e.toString());
      response = null;
    }
    return chartData;
  }

  List<ChartData> _convertDataToChartData(List<dynamic> data) {
    if (data.isEmpty) return [];
    try {
      return data.map((item) {
        try {
          return ChartData(
            "${item['label']}", // Replace 'x' with your actual key
            item['value'] as num, // Replace 'y' with your actual key
          );
        } catch (e) {
          return ChartData(
            "${item['label']}", // Replace 'x' with your actual key
            0, // Replace 'y' with your actual key
          );
        }
      }).toList();
    } catch (e) {
      print(e.toString());
      return [];
    }
  }

  @override
  void initState() {
    super.initState();
    fetchData(false);
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<ChartData>>(
      future: fetchData(false),
      builder: (context, snapshot) {
        if (snapshot.hasData && snapshot.data!.isNotEmpty) {
          if (widget.chartType == ChartType.gauge) {
            var configDataStr =
                widget.diagramConfig ?? ChartTypeConfig.byType[ChartType.gauge];
            return Gauge(
              // 10 + 30 * Random().nextDouble(),
              snapshot.data![snapshot.data!.length - 1].value.toDouble(),
              snapshot.data![snapshot.data!.length - 1].label,
              minValue: double.parse(configDataStr!["minValue"] ?? "10"),
              maxValue: double.parse(configDataStr["maxValue"] ?? "40"),
              segmentColors: const [Colors.blue, Colors.green, Colors.red],
              sweepAngle: double.parse(configDataStr["sweepAngle"] ?? "200"),
              majorTickStep:
                  double.parse(configDataStr["majorTickStep"] ?? "10"),
              medianTickStep:
                  double.parse(configDataStr["medianTickStep"] ?? "5"),
              minorTickStep:
                  double.parse(configDataStr["minorTickStep"] ?? "1"),
              widgetSize: const Size(250, 250),
            );
          } else {
            var chart = graphic.Chart(
              data: snapshot.data!,
              variables: {
                "label": graphic.Variable(
                    accessor: (ChartData point) => point.label),
                "value": graphic.Variable(
                    accessor: (ChartData point) => point.value),
              },
              marks: widget.chartType == ChartType.bar
                  ? [graphic.IntervalMark()]
                  : [
                      graphic.LineMark(
                        position:
                            graphic.Varset('label') * graphic.Varset('value'),
                      ),
                    ],
              axes: [
                graphic.Defaults.horizontalAxis,
                graphic.Defaults.verticalAxis,
              ],
              selections: {
                'tooltipMouse': graphic.PointSelection(on: {
                  graphic.GestureType.hover,
                }, devices: {
                  PointerDeviceKind.mouse
                }, dim: graphic.Dim.x),
                'tap': graphic.PointSelection(dim: graphic.Dim.x)
              },
              tooltip: graphic.TooltipGuide(
                selections: {'tooltipTouch', 'tooltipMouse', 'tap'},
                // followPointer: [true, true],
                align: Alignment.topLeft,
              ),
              crosshair: graphic.CrosshairGuide(
                selections: {'tooltipTouch', 'tooltipMouse', 'tap'},
                // followPointer: [false, true],
              ),
            );

            return chart;
          }
        } else if (snapshot.hasError) {
          return Text("${snapshot.error}");
        } else if (snapshot.hasData && snapshot.data!.isEmpty) {
          return const Text("NO DATA");
        }
        // By default, show a loading spinner.
        return const CircularProgressIndicator();
      },
    );
  }
}
