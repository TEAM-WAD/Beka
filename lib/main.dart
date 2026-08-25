import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:telegram_client/telegram_client.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const TelegramApp());
}

class TelegramApp extends StatelessWidget {
  const TelegramApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Telegram Debug App',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(0xFF17212B),
        appBarTheme: const AppBarTheme(backgroundColor: Color(0xFF242F3D)),
      ),
      home: const TelegramDebugScreen(),
    );
  }
}

class TelegramDebugScreen extends StatefulWidget {
  const TelegramDebugScreen({super.key});

  @override
  State<TelegramDebugScreen> createState() => _TelegramDebugScreenState();
}

class _TelegramDebugScreenState extends State<TelegramDebugScreen> {
  final Tdlib _tdlib = Tdlib();
  final int _clientId = 1;

  final int _apiId = 94575;
  final String _apiHash = 'a3406de8d171326e3c403d80a9b00a9c';

  final TextEditingController _phoneController = TextEditingController(text: '+964777001246');
  final TextEditingController _codeController = TextEditingController();

  final List<String> _logs = [];
  bool _showCodeInput = false;

  @override
  void initState() {
    super.initState();
    _addLog('بدء تشغيل التطبيق...');
    _setupTdlib();
  }

  void _addLog(String log) {
    setState(() {
      _logs.insert(0, "[${DateTime.now().toString().split(' ').last.substring(0, 8)}] $log");
    });
  }

  Future<void> _setupTdlib() async {
    try {
      _tdlib.createclient(clientId: _clientId);
      _addLog('تم إنشاء العميل (Client Created)');

      _tdlib.on(_tdlib.event_update, (UpdateTelegramClientTdlib update) {
        if (update.client_id == _clientId && update.raw is Map) {
          final rawMap = Map<String, dynamic>.from(update.raw);
          final type = rawMap['@type'];
          _addLog('تحديث جديد: $type');

          if (type == 'updateAuthorizationState') {
            final authState = rawMap['authorization_state']?['@type'];
            _addLog('حالة التخويل: $authState');

            if (authState == 'authorizationStateWaitTdlibParameters') {
              _sendParameters();
            } else if (authState == 'authorizationStateWaitCode') {
              setState(() => _showCodeInput = true);
            }
          }
        }
      });
    } catch (e) {
      _addLog('خطأ استثناء بالتهيئة: $e');
    }
  }

  Future<void> _sendParameters() async {
    _addLog('جاري إرسال setTdlibParameters...');
    final Directory appDocDir = await getApplicationDocumentsDirectory();
    final String dbPath = "${appDocDir.path}/td_db";

    final res = await _tdlib.invoke(
      'setTdlibParameters',
      parameters: {
        'api_id': _apiId,
        'api_hash': _apiHash,
        'system_language_code': 'ar',
        'device_model': 'Android',
        'application_version': '1.0.0',
        'database_directory': dbPath,
        'files_directory': dbPath,
        'use_secret_chats': true,
        'use_message_database': true,
        'use_file_database': true,
      },
      clientId: _clientId,
    );
    _addLog('استجابة المفاتيح: ${jsonEncode(res)}');
  }

  Future<void> _submitPhone() async {
    String phone = _phoneController.text.trim();
    if (phone.startsWith('+9640')) {
      phone = '+964${phone.substring(5)}';
      _phoneController.text = phone;
    }

    _addLog('جاري إرسال الرقم: $phone');

    // إرسال مباشر وبدون قيود
    await _sendParameters();

    final res = await _tdlib.invoke(
      'setAuthenticationPhoneNumber',
      parameters: {'phone_number': phone},
      clientId: _clientId,
    );

    _addLog('استجابة إرسال الرقم: ${jsonEncode(res)}');
  }

  Future<void> _submitCode() async {
    final code = _codeController.text.trim();
    _addLog('جاري إرسال كود التحقق: $code');

    final res = await _tdlib.invoke(
      'checkAuthenticationCode',
      parameters: {'code': code},
      clientId: _clientId,
    );

    _addLog('استجابة كود التحقق: ${jsonEncode(res)}');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('تشخيص اتصال تليجرام')),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            if (!_showCodeInput) ...[
              TextField(
                controller: _phoneController,
                keyboardType: TextInputType.phone,
                decoration: const InputDecoration(
                  labelText: 'رقم الهاتف',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 10),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _submitPhone, // مفعل دائماً لقطع التخمين
                  style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF64B5F6)),
                  child: const Text('إرسال الرقم الآن', style: TextStyle(color: Colors.black)),
                ),
              ),
            ] else ...[
              TextField(
                controller: _codeController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'رمز التحقق (Code)',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 10),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _submitCode,
                  style: ElevatedButton.styleFrom(backgroundColor: Colors.green),
                  child: const Text('تأكيد الكود', style: TextStyle(color: Colors.white)),
                ),
              ),
            ],
            const SizedBox(height: 16),
            const Align(
              alignment: Alignment.centerRight,
              child: Text('سجل الأحداث المباشر (Logs):', style: TextStyle(fontWeight: FontWeight.bold)),
            ),
            const SizedBox(height: 8),
            Expanded(
              child: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.black,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.white24),
                ),
                child: ListView.builder(
                  itemCount: _logs.length,
                  itemBuilder: (context, index) {
                    return Text(
                      _logs[index],
                      style: const TextStyle(color: Colors.greenAccent, fontSize: 12, fontFamily: 'monospace'),
                    );
                  },
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
