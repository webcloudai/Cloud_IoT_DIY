/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License 
*/
import 'dart:convert';
import 'package:cloud_iot_diy/dashboard_provider.dart';
import 'package:flutter/material.dart';
import 'multitype_diagram.dart';
import 'authentication_provider.dart';
import 'package:provider/provider.dart';
import 'package:http/http.dart' as http;
import 'project_config_base.dart';

enum ChartDataType { historical, telemetry }

class DiagramOfChoice extends StatefulWidget {
  final List<String> dataSourceList;
  final String? initialDataSource;
  final List<String>? initialDeviceEndPoints;
  final String? initialEndPoint;
  final String? initialChartType;
  final String? initialChartDataType;
  final Map<String, String>? initialDiagramConfigParameters;
  final bool? forceInitial;

  const DiagramOfChoice({
    Key? key,
    required this.dataSourceList,
    this.initialDataSource,
    this.initialDeviceEndPoints,
    this.initialEndPoint,
    this.initialChartType,
    this.initialChartDataType,
    this.initialDiagramConfigParameters,
    this.forceInitial,
  }) : super(key: key);

  @override
  DiagramOfChoiceState createState() => DiagramOfChoiceState();
}

class DiagramOfChoiceState extends State<DiagramOfChoice>
    with AutomaticKeepAliveClientMixin {
  String? selectedDataSource;
  String? selectedEndPoint;
  List<String>? endPointList;
  ChartType selectedChartType = ChartType.line;
  Map<String, String>? diagramConfigParameters =
      ChartTypeConfig.byType[ChartType.line];
  ChartDataType selectedChartDataType = ChartDataType.historical;
  String _accessToken = '';
  // some 'caching' properties
  Map endpointsByDevice = {};

  @override
  bool get wantKeepAlive => true;

  Future<List<ChartData>?> _fetchData(urlString) async {
    return [];
  }

  void getAccessToken() async {
    var authProvider =
        Provider.of<AuthenticationProvider>(context, listen: false);
    _accessToken = await authProvider.getAccessToken();
  }

  void getEndPointList(String dataSource) async {
    if (endpointsByDevice.containsKey(dataSource)) {
      endPointList = endpointsByDevice[dataSource];
      return;
    }
    getAccessToken();
    http.Response? response;
    try {
      response = await http.get(
        Uri.parse(ProjectConfig.getDeviceEndpoints(dataSource)),
        headers: {
          'Authorization': 'Bearer $_accessToken',
        },
      );
      if (response.statusCode == 200) {
        endPointList = (json.decode(response.body) as List)
            .map((item) => item as String)
            .toList();
        endpointsByDevice[dataSource] = endPointList;
        setState(() {});
      }
    } catch (e) {
      print(e.toString());
      response = null;
    }
  }

  Future<Map<String, String>?> _showDiagramConfigDialog(
      BuildContext context) async {
    if (diagramConfigParameters == null) return null;
    // prepare result map
    Map<String, String> updatedParameters =
        Map<String, String>.from(diagramConfigParameters!);

    return showDialog<Map<String, String>>(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: const Text('Configuration'),
          content: Column(
              children: updatedParameters.entries
                  .map((e) => TextField(
                        key: Key(e.key),
                        decoration: InputDecoration(
                          labelText: e.key,
                          hintText: e.value,
                        ),
                        keyboardType: TextInputType.number,
                        onChanged: (value) {
                          updatedParameters[e.key] = value;
                        },
                      ))
                  .toList()),
          actions: <Widget>[
            TextButton(
              onPressed: () {
                Navigator.of(context).pop();
              },
              child: const Text('Cancel'),
            ),
            TextButton(
              onPressed: () {
                Navigator.of(context).pop(updatedParameters);
              },
              child: const Text('Apply'),
            ),
          ],
        );
      },
    );
  }

  @override
  void initState() {
    super.initState();
    getAccessToken();

    if (widget.initialDataSource != null) {
      selectedDataSource = widget.initialDataSource;
      if (widget.forceInitial ?? false) {
        endpointsByDevice[selectedDataSource] = widget.initialDeviceEndPoints;
        endPointList = widget.initialDeviceEndPoints;
      }
      getEndPointList(selectedDataSource!);
    }
    if (widget.initialEndPoint != null) {
      selectedEndPoint = widget.initialEndPoint;
    }
    if (widget.initialChartType != null) {
      selectedChartType = ChartType.values.firstWhere(
          (e) => e.toString() == 'ChartType.${widget.initialChartType}');
    }
    if (widget.initialChartDataType != null) {
      selectedChartDataType = ChartDataType.values.firstWhere((e) =>
          e.toString() == 'ChartDataType.${widget.initialChartDataType}');
    }
    if (widget.initialDiagramConfigParameters != null) {
      diagramConfigParameters = widget.initialDiagramConfigParameters;
    }
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return Column(
      children: [
        Row(mainAxisAlignment: MainAxisAlignment.spaceAround, children: [
          // choose device (data source)
          SizedBox(
              width: 100,
              child: DropdownButton<String>(
                value: selectedDataSource,
                hint: const Text("device"),
                isExpanded: true,
                items: widget.dataSourceList.map((String value) {
                  return DropdownMenuItem<String>(
                    value: value,
                    child: Text(value),
                  );
                }).toList(),
                onChanged: (value) {
                  Provider.of<DashboardProvider>(context, listen: false)
                      .updateComponentState(
                    widget.key.toString(),
                    value, //selectedDataSource,
                    endpointsByDevice[value],
                    selectedEndPoint,
                    selectedChartDataType,
                    selectedChartType,
                    diagramConfigParameters,
                  );
                  setState(() {
                    selectedDataSource = value;
                    getEndPointList(value!);
                  });
                },
              )),
          // choose endpoint from the list
          if (endPointList != null)
            SizedBox(
                width: 150,
                child: DropdownButton<String>(
                  value: selectedEndPoint,
                  isExpanded: true,
                  items: endPointList!.map((String value) {
                    return DropdownMenuItem<String>(
                      value: value,
                      child: Text(value),
                    );
                  }).toList(),
                  onChanged: (value) {
                    Provider.of<DashboardProvider>(context, listen: false)
                        .updateComponentState(
                      widget.key.toString(),
                      selectedDataSource,
                      endPointList,
                      value, //selectedEndPoint,
                      selectedChartDataType,
                      selectedChartType,
                      diagramConfigParameters,
                    );
                    setState(() {
                      selectedEndPoint = value;
                    });
                  },
                ))
          else if (selectedDataSource == null)
            const Text("<- choose device!")
          else
            const CircularProgressIndicator(),
        ]),
        // Flexible(
        //     child:
        Row(mainAxisAlignment: MainAxisAlignment.spaceAround, children: [
          SizedBox(
              width: 100,
              child: DropdownButton<ChartDataType>(
                isExpanded: true,
                value: selectedChartDataType,
                // isExpanded: true,
                items: ChartDataType.values.map((ChartDataType type) {
                  return DropdownMenuItem<ChartDataType>(
                    value: type,
                    child: Text(type.toString().split('.').last),
                  );
                }).toList(),
                onChanged: (ChartDataType? newValue) {
                  Provider.of<DashboardProvider>(context, listen: false)
                      .updateComponentState(
                    widget.key.toString(),
                    selectedDataSource,
                    endPointList,
                    selectedEndPoint,
                    newValue, //selectedChartDataType,
                    selectedChartType,
                    diagramConfigParameters,
                  );
                  setState(() {
                    selectedChartDataType =
                        newValue!; // ?? ChartDataType.historical;
                  });
                },
                hint: const Text('Select what data type to chart'),
              )),
          SizedBox(
              width: 100,
              child: DropdownButton<ChartType>(
                isExpanded: true,
                value: selectedChartType,
                items: ChartType.values.map((ChartType type) {
                  return DropdownMenuItem<ChartType>(
                    value: type,
                    child: Text(type.toString().split('.').last),
                  );
                }).toList(),
                onChanged: (ChartType? newValue) {
                  Provider.of<DashboardProvider>(context, listen: false)
                      .updateComponentState(
                          widget.key.toString(),
                          selectedDataSource,
                          endPointList,
                          selectedEndPoint,
                          selectedChartDataType,
                          newValue ?? ChartType.line, //selectedChartType,
                          diagramConfigParameters);
                  setState(() {
                    selectedChartType = newValue ?? ChartType.line;
                    diagramConfigParameters =
                        ChartTypeConfig.byType[selectedChartType];
                  });
                },
                hint: const Text('Select a chart type'),
              )),
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () async {
              if (selectedChartType == ChartType.gauge) {
                final newConfig = await _showDiagramConfigDialog(context);
                if (newConfig != null) {
                  Provider.of<DashboardProvider>(context, listen: false)
                      .updateComponentState(
                    widget.key.toString(),
                    selectedDataSource,
                    endPointList,
                    selectedEndPoint,
                    selectedChartDataType,
                    selectedChartType,
                    newConfig, //diagramConfigParameters,
                  );
                  setState(() {
                    diagramConfigParameters = newConfig;
                  });
                }
              }
            },
          ),
          IconButton(
              onPressed: () {
                setState(
                    () {}); // This will trigger a rebuild of the chart widget
              },
              icon: const Icon(Icons.refresh)),
        ]),

        // Implementation below made with respect to potential future change
        //  when data for diagram will be collected here
        if (selectedEndPoint != null)
          Flexible(
            child: FutureBuilder<List<ChartData>?>(
              future: _fetchData('$selectedDataSource?$selectedEndPoint'),
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const CircularProgressIndicator();
                } else if (snapshot.hasError) {
                  return Text('Error: ${snapshot.error}');
                } else {
                  return ChartWidget(
                    apiUrl: ProjectConfig.getDataEndpoint(
                      selectedDataSource!,
                      selectedChartDataType.name,
                      selectedEndPoint!,
                      selectedChartType.name,
                    ),
                    accessToken: _accessToken,
                    chartType: selectedChartType,
                    diagramConfig: diagramConfigParameters,
                  );
                }
              },
            ),
          )
        else
          const Flexible(
              child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Padding(padding: EdgeInsets.all(50)),
              Icon(
                Icons.query_stats,
                size: 100,
              )
            ],
          )), //,
      ],
    );
  }
}
