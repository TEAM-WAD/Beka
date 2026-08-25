import 'package:flutter/material.dart';
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
      title: 'Telegram Native Custom',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(0xFF17212B),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF242F3D),
          elevation: 0,
        ),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF64B5F6),
          surface: Color(0xFF242F3D),
        ),
      ),
      home: const TelegramAuthOrMainScreen(),
    );
  }
}

class TelegramAuthOrMainScreen extends StatefulWidget {
  const TelegramAuthOrMainScreen({super.key});

  @override
  State<TelegramAuthOrMainScreen> createState() => _TelegramAuthOrMainScreenState();
}

class _TelegramAuthOrMainScreenState extends State<TelegramAuthOrMainScreen> {
  final Tdlib _tdlib = Tdlib();
  final int _clientId = 1;

  bool _isInitializing = true;
  bool _isAuthorized = false;
  bool _isSubmitting = false;
  
  String _authState = 'wait_parameters'; // wait_parameters, wait_phone, wait_code, ready
  String _statusMessage = 'جاري التهيئة...';

  final TextEditingController _phoneController = TextEditingController();
  final TextEditingController _codeController = TextEditingController();
  final TextEditingController _apiIdController = TextEditingController();
  final TextEditingController _apiHashController = TextEditingController();

  List<Map<String, dynamic>> _chats = [];

  @override
  void initState() {
    super.initState();
    _initTdlib();
  }

  Future<void> _initTdlib() async {
    try {
      _tdlib.createclient(clientId: _clientId);

      _tdlib.on(_tdlib.event_update, (UpdateTelegramClientTdlib update) {
        if (update.client_id == _clientId && update.raw is Map) {
          _handleUpdate(Map<String, dynamic>.from(update.raw));
        }
      });

      setState(() {
        _isInitializing = false;
      });
    } catch (e) {
      setState(() {
        _isInitializing = false;
        _statusMessage = 'خطأ في تهيئة المكتبة: $e';
      });
    }
  }

  void _handleUpdate(Map<String, dynamic> update) {
    final type = update['@type'];
    if (type == 'updateAuthorizationState') {
      final authState = update['authorization_state'];
      if (authState != null && authState is Map) {
        final authType = authState['@type'];
        setState(() {
          _isSubmitting = false;
          if (authType == 'authorizationStateWaitTdlibParameters') {
            _authState = 'wait_parameters';
          } else if (authType == 'authorizationStateWaitPhoneNumber') {
            _authState = 'wait_phone';
          } else if (authType == 'authorizationStateWaitCode') {
            _authState = 'wait_code';
          } else if (authType == 'authorizationStateReady') {
            _isAuthorized = true;
            _authState = 'ready';
            _loadChats();
          }
        });
      }
    }
  }

  Future<void> _sendTdlibParameters() async {
    final apiId = int.tryParse(_apiIdController.text.trim()) ?? 0;
    final apiHash = _apiHashController.text.trim();

    if (apiId == 0 || apiHash.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('يرجى إدخال API ID و API Hash')),
      );
      return;
    }

    setState(() => _isSubmitting = true);

    await _tdlib.invoke(
      'setTdlibParameters',
      parameters: {
        'api_id': apiId,
        'api_hash': apiHash,
        'system_language_code': 'ar',
        'device_model': 'Android Mobile',
        'application_version': '1.0.0',
        'database_directory': '/data/user/0/com.example.telegram_custom_native/app_flutter/tdlib',
        'use_secret_chats': true,
        'use_message_database': true,
        'use_file_database': true,
      },
      clientId: _clientId,
    );
  }

  Future<void> _sendPhoneNumber() async {
    final phone = _phoneController.text.trim();
    if (phone.isEmpty) return;

    setState(() => _isSubmitting = true);

    await _tdlib.invoke(
      'setAuthenticationPhoneNumber',
      parameters: {
        'phone_number': phone,
      },
      clientId: _clientId,
    );
  }

  Future<void> _sendCode() async {
    final code = _codeController.text.trim();
    if (code.isEmpty) return;

    setState(() => _isSubmitting = true);

    await _tdlib.invoke(
      'checkAuthenticationCode',
      parameters: {
        'code': code,
      },
      clientId: _clientId,
    );
  }

  Future<void> _loadChats() async {
    final res = await _tdlib.invoke(
      'getChats',
      parameters: {'limit': 30},
      clientId: _clientId,
    );

    if (res is Map && res['chat_ids'] is List) {
      final List chatIds = res['chat_ids'];
      List<Map<String, dynamic>> loadedChats = [];
      for (var id in chatIds) {
        final chatData = await _tdlib.invoke(
          'getChat',
          parameters: {'chat_id': id},
          clientId: _clientId,
        );
        if (chatData is Map) {
          loadedChats.add(Map<String, dynamic>.from(chatData));
        }
      }
      setState(() {
        _chats = loadedChats;
      });
    }
  }

  Future<void> _viewStoryStealth(int chatId, int storyId) async {
    final storyData = await _tdlib.invoke(
      'getStory',
      parameters: {
        'story_sender_chat_id': chatId,
        'story_id': storyId,
      },
      clientId: _clientId,
    );

    if (mounted) {
      showDialog(
        context: context,
        builder: (context) => AlertDialog(
          backgroundColor: const Color(0xFF242F3D),
          title: const Text('مشاهدة الاستوري (مخفي)', style: TextStyle(color: Colors.white)),
          content: Text(
            'تم جلب الاستوري بنجاح دون تسجيل أي مشاهدة للسيرفر!\n\n$storyData',
            style: const TextStyle(color: Colors.white70),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('إغلاق'),
            ),
          ],
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isInitializing) {
      return Scaffold(
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const CircularProgressIndicator(),
              const SizedBox(height: 16),
              Text(_statusMessage, style: const TextStyle(color: Colors.white70)),
            ],
          ),
        ),
      );
    }

    if (!_isAuthorized) {
      return Scaffold(
        appBar: AppBar(title: const Text('تسجيل الدخول - تليجرام الأصلي')),
        body: SingleChildScrollView(
          padding: const EdgeInsets.all(20.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 20),
              TextField(
                controller: _apiIdController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'API ID',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _apiHashController,
                decoration: const InputDecoration(
                  labelText: 'API Hash',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 12),
              ElevatedButton(
                onPressed: _isSubmitting ? null : _sendTdlibParameters,
                child: _isSubmitting
                    ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('1. إرسال مفاتيح API'),
              ),
              const Divider(height: 40),
              if (_authState == 'wait_phone' || _authState == 'wait_parameters') ...[
                TextField(
                  controller: _phoneController,
                  keyboardType: TextInputType.phone,
                  decoration: const InputDecoration(
                    labelText: 'رقم الهاتف (مع الرمز الدولي)',
                    hintText: '+964xxxxxxxxx',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: _isSubmitting ? null : _sendPhoneNumber,
                  style: ElevatedButton.styleFrom(minimumSize: const Size.fromHeight(48)),
                  child: _isSubmitting
                      ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Text('2. إرسال رقم الهاتف'),
                ),
              ],
              if (_authState == 'wait_code') ...[
                const SizedBox(height: 16),
                TextField(
                  controller: _codeController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'رمز التحقق (SMS Code)',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: _isSubmitting ? null : _sendCode,
                  style: ElevatedButton.styleFrom(minimumSize: const Size.fromHeight(48)),
                  child: _isSubmitting
                      ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Text('3. تأكيد الرمز ودخول التطبيق'),
                ),
              ],
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('محادثات تليجرام (وضع التخفي)'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadChats,
          ),
        ],
      ),
      body: _chats.isEmpty
          ? const Center(child: Text('لا توجد محادثات محملة حالياً'))
          : ListView.builder(
              itemCount: _chats.length,
              itemBuilder: (context, index) {
                final chat = _chats[index];
                final title = chat['title'] ?? 'محادثة ${chat['id']}';
                return ListTile(
                  leading: const CircleAvatar(
                    backgroundColor: Color(0xFF64B5F6),
                    child: Icon(Icons.person, color: Colors.white),
                  ),
                  title: Text(title, style: const TextStyle(color: Colors.white)),
                  subtitle: Text('ID: ${chat['id']}', style: const TextStyle(color: Colors.grey)),
                  trailing: IconButton(
                    icon: const Icon(Icons.visibility_off, color: Colors.lightBlueAccent),
                    tooltip: 'مشاهدة الاستوري بدون علم صاحبها',
                    onPressed: () => _viewStoryStealth(chat['id'], 1),
                  ),
                );
              },
            ),
    );
  }
}
