/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License 
*/
import 'package:flutter/material.dart';
import 'diagram_of_choice.dart';
import 'multitype_diagram.dart';
import 'dart:collection';
import 'project_config_base.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class DashboardComponentStateInfo {
  int tileIndex; // index defines the location starting from top-left and going right first
  String? dataSource; // device name
  List<String>? deviceEndPoints; // list of endpoints available for device
  String? endPoint; // particular endpoint on the device
  ChartDataType? chartDataType; // historical / telemetry / ...
  ChartType? chartType;
  Map<String, String>? diagramConfigParameters;

  DashboardComponentStateInfo(
      this.tileIndex,
      this.dataSource,
      this.deviceEndPoints,
      this.endPoint,
      this.chartDataType,
      this.chartType,
      this.diagramConfigParameters);

  static DashboardComponentStateInfo fromMap(Map serialized) {
    Map<String, String>? loadedDiagramConfigParameters;
    ChartDataType? loadedChartDataType = ChartDataType.telemetry;
    ChartType? loadedChartType = ChartType.line;
    try {
      loadedChartDataType = ChartDataType.values.firstWhere((e) =>
          e.toString() == 'ChartDataType.${serialized["chartDataType"]}');
    } catch (e) {
      print("Fail to load chartDataType with exception");
      print(e.toString());
    }
    try {
      loadedChartType = ChartType.values.firstWhere(
          (e) => e.toString() == 'ChartType.${serialized["chartType"]}');
    } catch (e) {
      print("Fail to load chartType with exception");
      print(e.toString());
    }
    try {
      loadedDiagramConfigParameters = {};
      (json.decode(serialized["diagramConfigParameters"])
              as Map<String, dynamic>)
          .forEach((k, v) {
        loadedDiagramConfigParameters![k] = v as String;
      });
    } catch (e) {
      print("Fail to load diagramConfigParameters with exception");
      print(e.toString());
    }
    return DashboardComponentStateInfo(
      serialized["tileIndex"],
      serialized["dataSource"],
      (json.decode(serialized["deviceEndPoints"]) as List)
          .map((item) => (item as String))
          .toList(),
      serialized["endPoint"],
      loadedChartDataType, //serialized["chartDataType"],
      loadedChartType, //serialized["chartType"],
      loadedDiagramConfigParameters, // serialized["diagramConfigParameters"],
    );
  }

  Map toMap() {
    return {
      "tileIndex": tileIndex,
      "dataSource": dataSource,
      "deviceEndPoints": json.encode(deviceEndPoints),
      "endPoint": endPoint,
      "chartDataType": chartDataType == null ? null : chartDataType!.name,
      "chartType": chartType == null ? null : chartType!.name,
      "diagramConfigParameters": json.encode(diagramConfigParameters),
    };
  }
}

class DashboardProvider with ChangeNotifier {
  // List<Widget> _items = [];
  // List<Widget> get items => _items;

  final LinkedHashMap<String, Widget> _components =
      LinkedHashMap<String, Widget>();
  LinkedHashMap<String, Widget> get tiles => _components;

  LinkedHashMap<String, DashboardComponentStateInfo> _componentStates =
      LinkedHashMap<String, DashboardComponentStateInfo>();
  LinkedHashMap<String, DashboardComponentStateInfo> get componentsStates =>
      _componentStates;

  List<String> availableDataSources = [];

  void updateComponentState(
      String id,
      String? dataSource,
      List<String>? deviceEndPoints, // list of endpoints available for device
      String? endPoint,
      ChartDataType? chartDataType,
      ChartType? chartType,
      Map<String, String>? diagramConfigParameters) {
    int indexFromId = int.parse(id.split('DiagramOfChoice')[1].split("'")[0]);
    _componentStates[id] = DashboardComponentStateInfo(
        indexFromId,
        dataSource,
        deviceEndPoints,
        endPoint,
        chartDataType,
        chartType,
        diagramConfigParameters);
    // notifyListeners();  - we don't need to notify listeners
  }

  List<Widget> getTiles() {
    List<Widget> result = [];
    _components.forEach((k, v) => result.add(v));
    return result;
  }

  /// Recreate ALL dashboard widgets (used for dashboard load and refresh)
  Future<void> refreshDashboard() async {
    // clean up current dashboard widgets
    // tiles.forEach((key, value) {
    //   _components.remove(key);
    // });
    _components.clear();
    // create new widgets using stored states
    componentsStates.forEach((key, value) {
      addPredefinedTile(availableDataSources, value, key);
    });
    notifyListeners();
  }

  void addTile(List<String> listOfAvailableDataSources) {
    String tileKey = 'DiagramOfChoice${_components.length}';
    _components[tileKey] = DiagramOfChoice(
        key: Key(tileKey), dataSourceList: listOfAvailableDataSources);
    notifyListeners();
  }

  void addPredefinedTile(List<String> listOfAvailableDataSources,
      DashboardComponentStateInfo tileState, String? predefinedTileKey) {
    String tileKey =
        predefinedTileKey ?? 'DiagramOfChoice${_components.length}';
    _components[tileKey] = DiagramOfChoice(
      key: Key(tileKey),
      dataSourceList: listOfAvailableDataSources,
      initialDataSource: tileState.dataSource,
      initialDeviceEndPoints: tileState.deviceEndPoints,
      initialEndPoint: tileState.endPoint,
      initialChartType: (tileState.chartType ?? ChartType.line).name,
      initialChartDataType:
          (tileState.chartDataType ?? ChartDataType.telemetry).name,
      initialDiagramConfigParameters: tileState.diagramConfigParameters,
      forceInitial: true,
    );
    // notifyListeners();
  }

  void removeTile(String key) {
    _components.remove(key);
    notifyListeners();
  }

  void removeTileAt(int index) {
    _components.remove('DiagramOfChoice$index');
    notifyListeners();
  }

  // void removeItem(int index) {
  //   _items.removeAt(index);
  //   notifyListeners();
  // }

  /// Load dashboard data from API and notify listeners
  Future<void> loadDashboardWithId(String dashboardName, accessToken) async {
    http.Response? response;
    try {
      response = await http.get(
          Uri.parse(
              ProjectConfig.getDashboard(Uri.encodeComponent(dashboardName))),
          headers: {
            "Authorization": "Bearer $accessToken",
            "Content-Type": "application/json"
          });
    } catch (e) {
      print(e.toString());
      response = null;
    }
    if (response != null && response.statusCode == 200) {
      print("---data collected---");
      print(response.body);
      try {
        _componentStates = {
          for (var v in (json.decode(response.body)["dashboard_data"] as List)
              .map((item) => DashboardComponentStateInfo.fromMap(item as Map))
              .toList())
            'DiagramOfChoice${v.tileIndex}': v
        } as LinkedHashMap<String, DashboardComponentStateInfo>;
        refreshDashboard();
      } catch (e) {
        print(e.toString());
        return;
      }
      // silently ADD ITEM to _tiles for every component in the _componentStates without notifying listeners
    } else {
      throw Exception('Failed to load the dashboard');
    }
    notifyListeners();
  }

  Future<void> saveDashboardAs(String dashboardName, accessToken) async {
    http.Response? response;
    try {
      response = await http.post(
          Uri.parse(
              ProjectConfig.getDashboard(Uri.encodeComponent(dashboardName))),
          body: json.encode({
            "dashboard_data":
                _componentStates.values.map((value) => value.toMap()).toList()
          }),
          headers: {
            "Authorization": "Bearer $accessToken",
            "Content-Type": "application/json"
          });
    } catch (e) {
      print(e.toString());
      response = null;
    }
    if (response != null && response.statusCode == 200) {
      print("---dashboard saved successfully---");
      print(response.body);
      return;
    } else {
      throw Exception('Failed to save the dashboard');
    }
  }
}
